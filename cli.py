#!/usr/bin/env python3

import os
import shlex
import sys
import textwrap

import backtrace
import pipcl

class ArgsEq:
    '''
    Enhanced iterator for list of arguments, optionally splitting args at '=',
    for example `--foo=bar`.
    
    >>> args = Args(shlex.split('--foo bar --qwert=123 --bar foo'))
    >>> while 1:
    ...     try:
    ...         arg = args.next(spliteq=1)
    ...         if arg.text is StopIteration:
    ...             break
    ...     except StopIteration:
    ...         break
    ...     print(arg.as_str())
    --foo
    bar
    --qwert
    123
    --bar
    foo
    
    >>> args = Args(shlex.split('--foo bar --qwert=123 --bar foo'))
    >>> while 1:
    ...     try:
    ...         arg = args.next(spliteq=1)
    ...         if arg.text is StopIteration:
    ...             break
    ...     except StopIteration:
    ...         break
    ...     print(arg.text)
    --foo
    bar
    --qwert
    123
    --bar
    foo
    
    '''
    def __init__(self, argv, pos=0):
        self.argv = argv
        self.pos = pos
        self.pos_sub = 0
        self.current = None
        self._returned_items = list()
        
    def next(self, spliteq=False):
        '''
        Returns (item, pos) for next item in self.argv. Does not raise
        exception on EOF.
        
            item:
                Text of next item on command line. Will be StopIteration (the
                class itself, not an instance of the class) if EOF.
            pos:
                (pos, pos_sub):
                    pos:
                        index into self.argv.
                    pos_sub:
                        Start of text within self.argv[pos], usually zero.
                        Will be non-zero and point to character after '=' if
                        <spliteq> is true and argv[pos] contains '=' and we are
                        returning the value.
        '''
        pos = (self.pos, self.pos_sub)
        if self.pos_sub:
            # Return text after `=`.
            assert self.argv[self.pos][self.pos_sub-1] == '='
            ret = self.argv[self.pos][self.pos_sub:]
            self.pos += 1
            self.pos_sub = 0
        else:
            assert self.pos <= len(self.argv), (
                    f'Calling code failed to terminate loop after StopIteration(). {self.pos=} {len(self.argv)=}'
                    )
            if self.pos == len(self.argv):
                #pipcl.log(f'Returning StopIteration.')
                ret = StopIteration
                self.pos += 1
            else:
                ret = self.argv[self.pos]
                eq = -1
                if spliteq and (eq := ret.find('=')) >= 0:
                    # '--foo=bar'. Return '--foo' and make next call return 'bar'.
                    self.pos_sub = eq + 1
                    ret = ret[:eq]
                else:
                    self.pos += 1
        self.current = ret
        self._returned_items.append((ret, pos))
        return ret, pos

    def replace(self, pos_a, pos_b, new_args):
        '''
        Replaces self.argv region pos_a:pos_b with <new_args> and
        resets position to <pos_a>.
        
        pos_a and pos_b are (pos, pos_sub) tuples.
        
        As of 2026-02-17 we require that pos_a and pos_b both have pos_sub=0 -
        we cannot yet replace `foo` or `bar` in `foo=bar`.
        '''
        pipcl.log(f'{pos_a=} {pos_b=} {new_args=}')
        a1, a2 = pos_a
        b1, b2 = pos_b
        assert a2 == 0
        assert b2 == 0
        self.argv[a1:b1] = new_args
        self.pos = a1
        self.pos_sub = a2
    
    def set(self, pos, new_arg):
        pos, subpos = pos
        arg = self.argv[pos]
        arg = arg[:subpos] + new_arg
        self.argv[pos] = arg
        #assert a2 == 0, f'Cannot handle {self.argv[a1]!r}, use `--foo bar`.'
        #self.argv[a1] = new_arg
    
    def set_bool(self, pos, value):
        '''
        Should be called with <pos> set to the arg following `--foo`.
        
        Changes `--foo` and `foo=...` to `--foo=<value>`.
        '''
        pos, pos_sub = pos
        if pos_sub:
            # <pos> is `bar` in `--foo=bar`.
            value2 = self.argv[pos][:pos_sub] + str(value)
            self.argv[pos] = value2
        else:
            # <pos> is the `--bar` in `--foo --bar`.
            self.argv[pos-1] += f'={value}'
    

class Completions:
    '''
    Keeps a record of argument completions.
    '''
    def __init__(self):
        self.items = list()
        self.pos = (-1, 0)
    
    def add(self, suggestion, pos):
        if pos < self.pos:
            pipcl.log(f'Was not expecting {pos=} < {self.pos=}.')
            self.items.clear()
            self.pos = pos
        if pos > self.pos:
            self.items.clear()
            self.pos = pos
        self.items.append(suggestion)
    
    def __repr__(self):
        ret = ''
        ret = f'{self.pos=}:\n'
        for suggestion in self.items:
            ret += f'    {suggestion!r}\n'
        return ret


class Arg:
    '''
    A command-line argument which automatically adds items to a Completion when
    compared or converted to a specific type.
    '''
    def __init__(self, text, pos, completions):
        '''
        text:
            A string or the class StopIteration.
        '''
        assert isinstance(text, str) or text is StopIteration
        self.text = text
        self.pos = pos
        self.completions = completions
        if pos > self.completions.pos:
            # This isn't strictly necessary because any examination of us that
            # implies a completion will clear existing completions, but it will
            # make for easier debugging of calling code to clear now.
            #pipcl.log(f'{pos=} {self.completions.pos=} {len(self.completions.items)=}')
            #pipcl.log(f'{self.completions.items=}')
            #Actually next line prevents listing of all completions on correct eof. Although
            # still fails if not args at all.
            self.completions.items.clear()
    
    def __eq__(self, rhs):
        #pipcl.log(f'Arg.__eq__() {rhs=}.')
        ret = (self.text == rhs)
        if not ret:
            # We assume that <rhs> would have been a valid value, so add to
            # completions.
            self.completions.add(rhs, self.pos)
        return ret
    
    def __repr__(self):
        #return f'{self.text=} {self.pos=} {self.completions=}.'
        return f'{self.text=} {self.pos=}.'
    
    def _as_bool(self):
        '''
        Returns our value converted to a bool. If no match we add to
        completions and raise.
        
        Internal because user code should call Args.get_bool().
        '''
        #pipcl.log(f'{self.text=}')
        # Our comparisons of <self> will add completions where they fail.
        if self in ('0', 'false', 'False'):
            return False
        elif self in ('1', 'true', 'True'):
            return True
        raise Exception(f'Unrecognised bool value: {self.text!r}')
    
    def as_float(self):
        '''
        Returns our value converted to a float. If no match we add `float` to
        completions and raise.
        '''
        try:
            return float(self.text)
        except Exception:
            self.completions.add(float, self.pos)
            raise
    
    def as_int(self):
        '''
        Returns our value converted to an int. If no match we add `int` to
        completions and raise.
        '''
        try:
            return int(self.text)
        except Exception:
            self.completions.add(int, self.pos)
            raise
    
    def as_str(self):
        '''
        Returns our value converted to an string. Only fails if we have reached
        EOF, in which case we add `str` to completions.
        '''
        if not isinstance(self.text, str):
            self.completions.add(str, self.pos)
            raise StopIteration()
        return self.text
    
    def as_text(self):
        '''
        Compatibility wrapper for as_str().
        '''
        return self.as_str()
    
    def startswith(self, rhs):
        '''
        Convenience fn saves caller from having to type `.as_str()`.
        '''
        if self.text is StopIteration:
            return False
        return self.text.startswith(rhs)


class Args:
    '''
    Enhanced args iterator, wrapping ArgsEq, that returns an Arg instead of a
    string, so we can gather completion information.
    '''
    def __init__(self, argv, pos=0):
        self.args_eq = ArgsEq(argv, pos=pos)
        self.completions = Completions()
        self.current = None # Always the last returned Arg.
    
    def __next__(self):
        '''
        Support Python iteration.
        '''
        return self.next()
    
    def next(self, spliteq=False):
        '''
        Returns an Arg for next item in argv.
        
        If we have reached EOF, the returned Arg has .text = StopIteration (the
        class itself, not an instance of the class).
        '''
        text, pos = self.args_eq.next(spliteq=spliteq)
        arg = Arg(text, pos, self.completions)
        self.current = arg
        #pipcl.log(f'Returning: {arg=}')
        return arg
    
    def error_text(self):
        '''
        Returns two-line text containing the command line and caret characters
        pointing to where the command line was incorrect.
        
        fixme: move this into ArgsEq.
        '''
        line1 = ''
        line2 = ''
        for i, (text, (_pos, pos_eq)) in enumerate(self.args_eq._returned_items):    # pylint: disable=protected-access)
            #if i:
            #    line1 += ' '
            #    line2 += ' '
            if text is StopIteration:
                line2 += '^'
            else:
                if i:
                    if pos_eq:
                        line1 += '='
                    else:
                        line1 += ' '
                    line2 += ' '
                t = shlex.quote(text)
                line1 += t
                if i+1 == len(self.args_eq._returned_items):    # pylint: disable=protected-access)
                    line2 += '^' * len(t)
                else:
                    line2 += ' ' * len(t)
        return f'{line1}\n{line2}\n'
    
    @property
    def argv(self):
        return self.args_eq.argv
    
    def get_bool(self, overwrite=None):
        '''
        Should be used to get bool args instead of Arg._as_bool(), in order
        to allow `--foo` to be treated as True. If current arg is the `--foo`
        in `--foo=true` we return true etc, but otherwise (`--foo`) we simply
        return True.
        
        If <overwrite> is not None, we modify argv to set the value to
        <overwrite>.
        '''
        pos = self.pos
        
        if self.args_eq.pos_sub:
            # <self> is the `--foo` in `--foo=...`.
            ret = self.next()._as_bool()    # pylint: disable=protected-access)
        else:
            # `--foo` is treated as True.
            ret = True
        if overwrite is not None:
            self.args_eq.set_bool(pos, overwrite)
        return ret
    
    @property
    def pos(self):
        return self.args_eq.pos, self.args_eq.pos_sub
    
    @property
    def suggestions(self):
        return self.completions.items
    
    def final(self):
        '''
        Handles command-line parsing errors and base completion. We write out
        completions if COMP_LINE is set. Otherwise we write out diagnostics if
        an exception is active.
        '''
        COMP_LINE = os.environ.get('COMP_LINE')
        #COMP_POINT = os.environ.get('COMP_POINT')
        #COMP_TYPE = os.environ.get('COMP_TYPE')
        _, exception, _ = sys.exc_info()
        
        def get_suggestions():
            '''
            If current arg matches the start of one or more suggestions, we
            return only these matching suggestions. Otherwise we return all
            suggestions.
            
            This appears to make bash do what we want without us considering
            COMP_TYPE. Perhaps COMP_TYPE is only required for non-dynamic
            completion?
            '''
            n_match = 0
            #pipcl.log(f'{self.suggestions=}')
            for suggestion in self.suggestions:
                if isinstance(self.current.text, str) and suggestion.startswith(self.current.text):
                    n_match += 1
            ret = ''
            for suggestion in self.suggestions:
                if n_match == 0 or (isinstance(self.current.text, str) and suggestion.startswith(self.current.text)):
                    ret += f'    {suggestion}\n'
            return ret.rstrip()
            
        if exception:
            # Exception has been raised.
            #print(f'{self.suggestions=}')
            if COMP_LINE:
                text = get_suggestions()
                pipcl.log(f'get_suggestions() => {text=}')
                #sq = "'"
                #pipcl.log(f'{sq in text=}')
                sys.stdout.write(text)
                sys.exit()
            else:
                text = ''
                text += 'Bad command line\n'
                text += self.error_text()
                if isinstance(exception, StopIteration):
                    text += f'Ran out of arguments.\n'
                text += f'Expected one of:\n'
                text += get_suggestions()
                raise Exception(text.strip()) from exception
                
        else:
            if COMP_LINE:
                show_all = False
                for suggestion in self.suggestions:
                    if isinstance(self.current.text, str) and suggestion.startswith(self.current.text):
                        break
                else:
                    show_all = True
                for suggestion in self.suggestions:
                    if show_all or suggestion.startswith(self.current.text):
                        print(suggestion)
                sys.exit(0)


def check_cl(command, expected, expected_error_text=None, expected_completions=None):
    print(f'Testing:')
    print(f'    {command=}')
    print(f'    {expected=}')
    argv = shlex.split(command)
    args = Args(argv)
    args.next()
    items = list()
    error_text = None
    try:
        while 1:
            try:
                arg = args.next(spliteq=1)
                #if arg.text is StopIteration:
                #    break
            except StopIteration:
                pipcl.log(f'Exception: StopIteration')
                break
            if isinstance(arg.text, str):
                items.append(arg.as_str())
            pipcl.log(f'{arg=}')
            if arg == '-i':
                item = args.next().as_int()
            elif arg == '--foo':
                item = args.next().as_str()
            elif arg == '-f':
                item = args.next().as_float()
            elif arg.text is StopIteration:
                pipcl.log(f'StopIteration => break. {args.completions=} {args.completions.items=}')
                break
            else:
                assert 0, f'Unexpected {arg=}.'
            items.append(item)
    except Exception as ee:
        e = ee
        error_text = args.error_text()
        print(f'Exception: {e=}')
        backtrace.show()
    else:
        e = None
    
    if expected_completions is not None:
        print(f'{expected_completions=}')
        print(f'{args.completions.items=}')
        assert args.completions.items == expected_completions
        
    print(f'       {items=}')
    if error_text:
        print(f'    error_text:\n{textwrap.indent(error_text, "        ")}')
    if expected_error_text:
        print(f'    error_text:\n{textwrap.indent(expected_error_text, "        ")}')
    
    assert items == expected, f'\n{expected=}\n   {items=}'
    
    assert error_text == expected_error_text, ('\n'
            f'{expected_error_text=}\n'
            f'         {error_text=}\n'
            )
    print(f'    Ok.')

def test():
    check_cl(
            'prog -i 23 --foo=bar -f=0.234 -i 123',
            [
                '-i',
                23,
                '--foo',
                'bar',
                '-f',
                0.234,
                '-i',
                123,
            ],
            )
    check_cl(
            'prog -i 23 --foo=bar -f=0.234 -i 12.3',
            [
                '-i',
                23,
                '--foo',
                'bar',
                '-f',
                0.234,
                '-i',
            ],
            
            'prog -i 23 --foo=bar -f=0.234 -i 12.3\n'
            '                                 ^^^^\n'
            )
    
    check_cl(
            'prog',
            expected=[],
            expected_completions=['-i', '--foo', '-f'],
            )
    
    check_cl(
            'prog -i',
            expected=['-i'],
            expected_error_text='prog -i\n       \n',
            expected_completions=[int],
            )


if __name__ == '__main__':
    test()
