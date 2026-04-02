#! /usr/bin/env python3

'''
Alternatives to Python's default traceback module.
'''

import inspect
import io
import os
import sys
import traceback
import types


def exception_hook(_type, exception, _traceback):
    '''
    Wrapper for `show()` suitable for use as `sys.excepthook`.
    '''
    show(exception)


def exception_hook_install():
    '''
    Sets sys.excepthook and threading.excepthook to call show().
    '''
    import threading
    sys.excepthook = exception_hook
    threading.excepthook = exception_hook
    

def show(
        exception_or_traceback = None,
        limit = None,
        file = None,
        chain = True,
        *,
        outer = True,
        show_exception_type = True,
        reverse = False,
        reverse_chain = False,
        framef = None,
        brief = False,
        ):
    '''
    Shows an exception and/or backtrace.

    This is an alternative to `traceback.*` functions that print/return
    human-readable representation of exceptions and backtraces, such as:

        * `traceback.print_exc()`
        * `traceback.print_exception()`
        * `traceback.print_stack()`
        * `traceback.print_tb()`

    Returns `None`, or the generated text if `file` is `str`.

    Args:
        exception_or_traceback:
            One of the following:
            
            * `None`: We use current exception from `sys.exc_info()` if set,
              otherwise the current backtrace from `inspect.stack()`.
            * A `BaseException` exception instance.
            * Something usable as `backtrace.show_frames()`'s `tb` arg, e.g.
              a `traceback.StackSummary`, a `types.TracebackType` or a list of
              frames.
        limit:
            Controls how many frames to include in backtraces; see
            `show_frames()` `limit` arg.
        file:
            As in `traceback.*()` functions: a file-like object to which we
            write output, or `sys.stderr` if `None`. Special value `str` makes
            us return our output as a string.
        chain:
            As in `traceback.*()` functions: if true (the default) we show
            chained exceptions as described in PEP-3134.
            
            If `outer` is true we show the entire backtrace of the inner-most
            exception, and just the inner frames of the chained exception(s).
        outer:
            If true (the default) we also show an exception's outer frames
            above the `catch` block (see `backtrace.show_frames()` for
            details). Otherwise we do not show outer frames, similar to
            `traceback.*()` functions. We use `outer=False` internally for
            chained exceptions to avoid duplication.
        show_exception_type:
            Controls whether exception text is prefixed by the type of
            the exception.
            
            * If callable, we include prefix if
              `show_exception_type(exception)` is true.
            * Otherwise if true (the default) we include the prefix for all
              exceptions (this mimcs the behaviour of `traceback.*()`
              functions).
            * Otherwise we exclude the prefix for all exceptions.
        reverse:
            If false (the default) we show any exception then a backtrace
            with inner frames first. Otherwise we show a backtrace with inner
            frames last followed by any exception, similar to `traceback.*()`
            functions. In both cases the exception is shown next to the frame
            that raised it, which helps readability.
        reverse_chain:
            If false (the default) we output inner exceptions first (error
            bar caused error foo), otherwise we output outer exceptions first
            ('error foo because error bar').
        framef:
            See `show_frame()`'s `framef` arg.
        brief:
            If true we generate shorter explanatory text.
    
    Install as system default with `backtrace.exception_hook_install()`.

    Examples:

        We use some defaults to allow testing with doctest:
        
        * We use `file=sys.stdout`.
        * We set `framef=show_framef_doctest` to allow matching to work.
        * We set `limit=main` to terminate backtraces at the outer-most
          function, excluding unknowable outer frames inside doctest.

        Basic handling of an exception:
        
            >>> def b():
            ...     raise Exception('b() failed')
            >>> def a():
            ...     try:
            ...         b()
            ...     except Exception as e:
            ...         show(e, file=sys.stdout, limit=main, framef=show_framef_doctest)
            >>> def main():
            ...     a()

            Calling `main()` shows the exception followed by traceback:
            
            >>> main()
            Exception: b() failed
            Traceback (most recent call first):
                b(): raise Exception('b() failed')
                a(): b()
                ^raise except:
                a(): show(e, file=sys.stdout, limit=main, framef=show_framef_doctest)
                main(): a()
            
        Handling of chained exceptions:
        
            >>> def d():
            ...     raise Exception('d(): deliberate error')
            >>> def c():
            ...     d()
            >>> def b():
            ...     try:
            ...         c()
            ...     except Exception as e:
            ...         raise Exception('b: c() failed') from e
            >>> def a():
            ...     try:
            ...         b()
            ...     except Exception as e:
            ...         show(file=sys.stdout, limit=main, reverse=g_reverse, chain=g_chain, reverse_chain=g_reverse_chain, framef=show_framef_doctest)
            >>> def main():
            ...     a()

            We output low-level exceptions first (matching what `traceback.*()`
            do), which also corresponds to our inner-first ordering of frames
            within backtraces:

            >>> g_reverse = False
            >>> g_chain = True
            >>> g_reverse_chain = False
            >>> main()
            Exception: d(): deliberate error
            Traceback (most recent call first):
                d(): raise Exception('d(): deliberate error')
                c(): d()
                b(): c()
                ^raise except:
                b(): raise Exception('b: c() failed') from e
                a(): show(file=sys.stdout, limit=main, reverse=g_reverse, chain=g_chain, reverse_chain=g_reverse_chain, framef=show_framef_doctest)
                main(): a()
            <BLANKLINE>
            The above exception was the direct cause of the following exception:
            Exception: b: c() failed
            Traceback (most recent call first):
                b(): raise Exception('b: c() failed') from e
                a(): b()

            Setting `reverse` to `True` reverses the order of frames with
            backtraces (which matches what `traceback.*()`), and `reverse_chain
            = True` also reverses the order of chained exceptions.
            
            >>> g_reverse = True
            >>> g_reverse_chain = True
            >>> main()  # doctest: +REPORT_UDIFF +ELLIPSIS
            Traceback (most recent call last):
                a(): b()
                b(): raise Exception('b: c() failed') from e
            Exception: b: c() failed
            <BLANKLINE>
            The above exception was directly caused by the following exception:
            Traceback (most recent call last):
                main(): a()
                a(): show(file=sys.stdout, limit=main, reverse=g_reverse, chain=g_chain, reverse_chain=g_reverse_chain, framef=show_framef_doctest)
                b(): raise Exception('b: c() failed') from e
                ^except raise:
                b(): c()
                c(): d()
                d(): raise Exception('d(): deliberate error')
            Exception: d(): deliberate error
            
            Setting chain to false only shows the current exception:
            
            >>> g_chain = False
            >>> g_reverse = False
            >>> main()  # doctest: +REPORT_UDIFF +ELLIPSIS
            Exception: b: c() failed
            Traceback (most recent call first):
                b(): raise Exception('b: c() failed') from e
                a(): b()
                ^raise except:
                a(): show(file=sys.stdout, limit=main, reverse=g_reverse, chain=g_chain, reverse_chain=g_reverse_chain, framef=show_framef_doctest)
                main(): a()
        
        Show current backtrace by using default `exception_or_traceback=None`:
        
            >>> def b():
            ...     show(file=sys.stdout, limit=main, reverse=g_reverse, framef=show_framef_doctest)
            >>> def a():
            ...     return b()
            >>> def main():
            ...     return a()

            >>> g_reverse = False
            >>> main()
            Traceback (most recent call first):
                b(): show(file=sys.stdout, limit=main, reverse=g_reverse, framef=show_framef_doctest)
                a(): return b()
                main(): return a()

            Set `reverse` to true to show most recent call last:
        
            >>> g_reverse = True
            >>> main() # doctest: +REPORT_UDIFF +ELLIPSIS
            Traceback (most recent call last):
                main(): return a()
                a(): return b()
                b(): show(file=sys.stdout, limit=main, reverse=g_reverse, framef=show_framef_doctest)

        Show an exception's `.__traceback__` backtrace:
        
            >>> def b():
            ...     raise Exception('foo') # raise
            >>> def a():
            ...     return b()  # call b
            >>> def main():
            ...     try:
            ...         a() # call a
            ...     except Exception as e:
            ...         show(e.__traceback__, limit=main, file=sys.stdout, framef=show_framef_doctest)

            Calling `main()` gives:
            
            >>> main()
            Traceback (most recent call first):
                b(): raise Exception('foo') # raise
                a(): return b()  # call b
                main(): a() # call a
                ^raise except:
                main(): show(e.__traceback__, limit=main, file=sys.stdout, framef=show_framef_doctest)
    '''
    if isinstance(exception_or_traceback, (types.TracebackType, traceback.StackSummary)):
        # Simple backtrace, no Exception information.
        exception = None
        tb = exception_or_traceback
    elif isinstance(exception_or_traceback, BaseException):
        exception = exception_or_traceback
        tb = exception.__traceback__
    elif exception_or_traceback is None:
        # Show exception if available, else traceback.
        _, exception, _ = sys.exc_info()
        if exception:
            tb = exception.__traceback__
        else:
            tb = inspect.stack()[1:]
            tb.reverse()    # Convert to inner frames last.
    else:
        assert 0, f'Unrecognised exception_or_traceback {type(exception_or_traceback)=} {exception_or_traceback=}.'

    out = io.StringIO() if file is str else file if file else sys.stderr

    def do_chain(exception):
        '''
        Recursively call ourselves for chained exceptions.
        '''
        show(
                exception,
                limit=limit,
                file=out,
                chain=chain,
                outer=outer,
                show_exception_type=show_exception_type,
                reverse=reverse,
                framef=framef,
                )

    if chain and exception and not reverse_chain:
        # Output any inner chained exception(s) before current exception.
        if exception.__cause__:
            do_chain(exception.__cause__)
            if brief:
                out.write('Which caused:\n')
            else:
                out.write('\nThe above exception was the direct cause of the following exception:\n')
            outer = False
        elif exception.__context__:
            do_chain(exception.__context__)
            if brief:
                out.write('Failed to handle because:\n')
            else:
                out.write('\nDuring handling of the above exception, another exception occurred:\n')
            outer = False

    def write_exception():
        if not exception:
            return
        if callable(show_exception_type):
            show = show_exception_type(exception)
        else:
            show = show_exception_type
        if show:
            for line in traceback.format_exception_only(type(exception), exception):
                out.write(line)
        else:
            out.write(f'{exception}\n')

    def write_tb():
        outer2 = outer
        if chain and reverse_chain and exception and (exception.__cause__ or exception.__context__):
            outer2 = False
        show_frames(tb, limit=limit, file=out, outer=outer2, reverse=reverse, framef=framef)
    
    # Write current exception.
    if reverse:
        # Most recent frame last so print traceback then exception.
        write_tb()
        write_exception()
    else:
        # Most recent frame first so print exception then traceback.
        write_exception()
        write_tb()

    if chain and exception and reverse_chain:
        # Output any inner chained exception(s) after current exception.
        if exception.__cause__:
            if brief:
                out.write(f'\nBecause: ')
            else:
                out.write(f'\nThe above exception was directly caused by the following exception:\n')
            do_chain(exception.__cause__)
        elif exception.__context__:
            if brief:
                out.write(f'While handling: ')
            else:
                out.write(f'\nThe above exception was raised during handling of the following exception:\n')
            do_chain(exception.__context__)

    if file is str:
        return out.getvalue()


def show_frames(tb=None, *, limit=None, file=None, outer=True, reverse=False, framef=None):
    '''
    Generates a text representation of a backtrace.
    
    Can also be used as drop-in replacement for `traceback.print_tb()`.
    
    Args:
        tb:
          * `None`: we use `inspect.stack()`, which returns a list of
            `inspect.FrameInfo`'s.
          * A `list`; must contain instances of:
          
            * `inspect.FrameInfo`, typically from `reversed(inspect.stack())`.
            * `traceback.FrameSummary`, typically from
              `traceback.extract_stack()`.  This does not contain function
              bytecode information, so setting `limit` to a function or a
              function's `.__code__` will not work.
            * `types.TracebackType`, does not typically occur, but supported just
              in case.
            
            We assume the list starts with the outer-most frame.
          * A `traceback.StackSummary`, typically from
            `traceback.extract_stack()`. This is also a list of
            `traceback.FrameSummary`'s, and is treated as described above.
          * A `types.TracebackType`; this identifies a particular stack frame
            and we assume it is from an `Exception`'s `.__traceback__` member. We
            use `inspect.getinnerframes()` and `inspect.getouterframes()` to get
            separate backtrace information above/below the try/catch blocks.
        
        limit:
          As in `traceback.*` functions:
        
          * `None`: show all frames.
          * positive `int`: show `limit` inner-most frames.
          * negative `int`: exclude `abs(limit)` outer-most frames.
          * Zero `int`: do not show backtrace.
          
          Can also be a function name, a function or a function's `bytecode`:
          
          * This terminates the backtrace at the specified function if it is
            found in the backtrace - no further outer frames are shown.
        
          * See `backtrace.show_frame()`'s `limit` arg for details.
        
        file:
            As in `traceback.*` functions: file-like object to which we write
            output, or `sys.stderr` if `None`. Special value `str` makes us
            return our output as a string.
        
        outer:
            If true (the default) and `tb` is a `types.TracebackType`, we also
            show frames outside of the `catch` block (see below for details).
        
        reverse:
            If true, we show inner frames last (like `traceback.*()`
            functions), otherwise (the default) we show inner frames last.
        
        framef:
            Format of each frame; see `show_frame()`'s `framef` arg for details.
    
    Differences from `traceback.*()` functions:

        * We default to showing the inner frames first; set `reverse` to true
          to show inner frames last.
        
        * Frames are displayed as one line in the form::

            <file>:<line>:<function>(): <text>

        * Filenames are displayed as relative to the current directory if
          applicable.

        * Outer frames are included when showing exception backtraces:
        
            Unlike `traceback.*` functions, the output for exceptions include
            outer stack frames beyond the point at which an exception was
            caught - i.e. frames from the top-level <module> or thread creation
            to the catch block. This can be disabled by setting `outer` to
            false.
            
            [For example see:
            https://stackoverflow.com/questions/42328723/traceback-print-exc-shows-incomplete-stack-trace].

        * The backtrace for an exception has three lines for the function that
          has caught the exception:
            
          * The location in the try block.
          * A marker line `^raise except:` where `^raise:` refers upwards to
            the inner frames that raised the exception and `except:` refers
            downwards to the outer frames that caught the exception.
          * The location in the `except` block.
          
          If `reverse` is true, these three lines are in the reverse order, and
          the marker line will be `^except raise:`.

        So the backtrace for an exception looks like this::

            <file>:<line>:<fn_c>: raise ... [where the exception was raised.]
            ...                             [... other frames]
            <file>:<line>:<fn_b>: <text>    [in `try:` block.]
            ^raise except:                  [marker line]
            <file>:<line>:<fn_b>: <text>    [in `except:` block.]
            ...                             [... other frames]
            <file>:<line>:<fn_a>: <text>    [in root module.]
    
    Basic operation showing current backtrace:
    
    >>> def b():
    ...     show_frames(file=sys.stdout, limit=main, framef=show_framef_doctest)
    >>> def a():
    ...     b()
    >>> def main():
    ...     a()
    
    >>> main()
    Traceback (most recent call first):
        b(): show_frames(file=sys.stdout, limit=main, framef=show_framef_doctest)
        a(): b()
        main(): a()
    
    Mimic `traceback.*()`'s default layout:
    
    >>> def b():
    ...     show_frames(file=sys.stdout, limit=main, reverse=1, framef=show_framef_0)
    >>> main()  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      File "<doctest ...[2]>", line 2, in main
        a()
      File "<doctest ...[1]>", line 2, in a
        b()
      File "<doctest ...[4]>", line 2, in b
        show_frames(file=sys.stdout, limit=main, reverse=1, framef=show_framef_0)
    
    For reference, here's `traceback.*()`'s default layout:
    
    >>> def b():
    ...     traceback.print_stack(file=sys.stdout, limit=3)
    >>> main()  # doctest: +ELLIPSIS
      File "<doctest ...[2]>", line 2, in main
        a()
      File "<doctest ...[1]>", line 2, in a
        b()
      File "<doctest ...[6]>", line 2, in b
        traceback.print_stack(file=sys.stdout, limit=3)
    
    Show just 2 inner-most frames:
    
    >>> def b():
    ...     show_frames(file=sys.stdout, limit=2, framef=show_framef_doctest)
    >>> main()
    Traceback (most recent call first):
        b(): show_frames(file=sys.stdout, limit=2, framef=show_framef_doctest)
        a(): b()
    
    Use a `traceback.StackSummary` from `traceback.extract_stack()`. Note that
    function bytecode information will not be available so we set `limit` to
    the function name 'main', not the function `main` itself.
    
    >>> def b():
    ...     tb = traceback.extract_stack()
    ...     assert isinstance(tb, traceback.StackSummary)
    ...     assert isinstance(tb, list)
    ...     for i in tb:
    ...         assert isinstance(i, traceback.FrameSummary)
    ...     show_frames(tb, file=sys.stdout, limit='main', framef=show_framef_doctest)
    
    >>> main()
    Traceback (most recent call first):
        b(): tb = traceback.extract_stack()
        a(): b()
        main(): a()
    
    Use an `Exception`'s `.__traceback__` member (which will be a
    `types.TracebackType`). This will show information about the locations
    within the `try` and `catch` blocks:
    
    >>> def b():
    ...     try:
    ...         raise Exception('foo')
    ...     except Exception as e:
    ...         tb = e.__traceback__
    ...     assert isinstance(tb, types.TracebackType)
    ...     inner = inspect.getinnerframes(tb)
    ...     for f in inner:
    ...         assert isinstance(f, inspect.FrameInfo)
    ...     show_frames(tb, file=sys.stdout, limit=main, framef=show_framef_doctest)
    
    >>> main()
    Traceback (most recent call first):
        b(): raise Exception('foo')
        ^raise except:
        b(): show_frames(tb, file=sys.stdout, limit=main, framef=show_framef_doctest)
        a(): b()
        main(): a()
    
    Exclude the 2 outer-most frames.
    
    >>> def b(limit):
    ...     return show_frames(file=str, limit=limit, framef=show_framef_doctest)
    >>> def a(limit):
    ...     return b(limit)
    >>> def main(limit=main):
    ...     return a(limit)
    >>> t1 = main(None)
    >>> t2 = main(-2)
    >>> print(t1) # doctest: +REPORT_UDIFF +ELLIPSIS
    Traceback (most recent call first):
        b(): return show_frames(file=str, limit=limit, framef=show_framef_doctest)
        a(): return b(limit)
        main(): return a(limit)
        <module>(): t1 = main(None)
        ...
    >>> print(t2) # doctest: +REPORT_UDIFF +ELLIPSIS
    Traceback (most recent call first):
        b(): return show_frames(file=str, limit=limit, framef=show_framef_doctest)
        a(): return b(limit)
        main(): return a(limit)
        <module>(): t2 = main(-2)
        ...
    
    >>> l1 = t1.split('\\n')
    >>> l2 = t2.split('\\n')
    >>> assert len(l2) == len(l1) - 2, f'{len(l2)=} {len(l1)=}'
    >>> for i in range(5, len(l2)-1):
    ...     assert l1[i] == l2[i]
    '''
    assert limit is None or isinstance(limit, (int, bytes, str)) or callable(limit), \
        f'Unrecognised {type(limit)=} should be None, int, bytes, str or callable.'
    
    if limit == 0:
        return
    if not tb:
        tb = inspect.stack()[1:]
        tb.reverse()    # Convert to inner frames last.

    out = io.StringIO() if file is str else file if file else sys.stderr
    cwd = os.getcwd() + os.sep
    outer_frames = list()
    
    if isinstance(tb, list):
        # (This happens if `tb` is a traceback.StackSummary.)
        # We assume this is inner-most frame last.
        inner_frames = tb
    elif isinstance(tb, types.TracebackType):
        inner_frames = inspect.getinnerframes(tb)   # inner-most frame last.
        if outer:
            outer_frames = inspect.getouterframes(tb.tb_frame)  # inner-most frame first.
    else:
        assert 0, f'Unrecognised {type(tb)=}.'

    frames = list()
    # If outer_frames, we join inner and outer with special double-frame item, which
    # ends up being represented as frame1+'^raise except:'+frame2 etc.
    if reverse:
        if outer_frames:
            # Join with (frame1, frame2).
            outer_frames.reverse()  # Convert to inner-most frame last.
            frames += outer_frames[:-1]
            frames.append((outer_frames[-1], inner_frames[0]))
            frames += inner_frames[1:]
        else:
            frames = inner_frames
        out.write('Traceback (most recent call last):\n')
    else:
        inner_frames.reverse()  # Convert to inner-most frame first.
        if outer_frames:
            # Join with (frame1, frame2).
            frames += inner_frames[:-1]
            frames.append((inner_frames[-1], outer_frames[0]))
            frames += outer_frames[1:]
        else:
            frames += inner_frames
        out.write('Traceback (most recent call first):\n')
    
    if isinstance(limit, int) and limit != 0:
        # Trim outer frames.
        frames = frames[-limit:] if reverse else frames[:limit]
    
    lines = list()
    for frame in frames:
        if isinstance(frame, tuple) and len(frame) == 2:
            f1, f2 = frame
            t1, m1 = show_frame(f1, limit, cwd, framef)
            t2, m2 = show_frame(f2, limit, cwd, framef)
            tmid = '    ^except raise:\n' if reverse else '    ^raise except:\n'
            text = t1 + tmid + t2
            assert m1 == m2
            match = m1
        else:
            text, match = show_frame(frame, limit, cwd, framef=framef)
        lines.append(text)
        if match:
            # No more outer frames from here.
            if reverse:
                lines = lines[-1:]
            else:
                break
    for line in lines:
        out.write(line)

    if file is str:
        return out.getvalue()


# Format for `show_frame()` - mimic `traceback.*()` functions:
show_framef_0 = '  File "{file}", line {line}, in {fn}\n    {text}\n'

# Format for `show_frame()` - concise format with one line per frame.
show_framef_1 = '    {file}:{line}:{fn}(): {text}\n'

# Format for `show_frame()` - simplified format for use with doctest.
show_framef_doctest = '    {fn}(): {text}\n'

# Format for `show_frame()` - default format.
show_framef_default = show_framef_1

def show_frame(frame, limit=None, cwd='', framef=None):
    '''
    Generates a text representation of a stack frame.
    
    Args:
        frame:
            Should be one of:
            
            * `traceback.FrameSummary`
            * `types.TracebackType`
            * `inspect.FrameInfo`
        limit:
            Used to set the returned `match` value.
            
            * `None`: always return with `match` set to False.
            * A function name, a function or a function's `bytecode`.
              
              This sets `match` to True if `frame` is for the same function
              name, or function codeblock. Typically a caller will then omit
              any further outer frames.

              * Specifying a function or a function's `bytecode` will
                not work with `traceback.FrameSummary`'s (typically from
                `traceback.extract_stack()`) because they do not contain
                function bytecode information.
        cwd:
            The current directory; used to strip the current directory when
            showing filenames.
        framef:
            A string that defines the format to use; `{file}`, `{line}`, `{fn}`
            and `{text}` are replaced by the corresponding frame data (using
            `str.format()`).
            
            See `show_framef_*` for convenient values.
    
    Returns `(text, match)`:
    
        * `text`: representation of stack frame.
        * `match`: bool - true iff frame's function (a `callable`), code
        (`codebytes`) or function name (`str`) matches `limit`.
    '''
    if framef is None:
        framef = show_framef_default
    match = False
    if isinstance(frame, traceback.FrameSummary):
        filename, line, fnname, text = frame
        code = None
    elif isinstance(frame, (types.TracebackType, inspect.FrameInfo)):
        f, filename, line, fnname, text, _index = frame
        text = text[0] if text else ''
        code = f.f_code
    else:
        assert 0, f'Unrecognised {type(frame)=} {frame=}.'
    text = text.strip() if text else ''
    if filename.startswith(cwd):
        filename = filename[ len(cwd):]
    if filename.startswith(f'.{os.sep}'):
        filename = filename[ 2:]
    text = framef.format(file=filename, line=line, fn=fnname, text=text)
    if (0   # pylint: disable=too-many-boolean-expressions
            or (limit == fnname)
            or (code and code == limit)
            or (code and code == getattr(limit, '__code__', None))
            ):
        match = True
    return text, match


def _demo2():
    try:
        raise Exception('_demo2 deliberate error')
    except Exception as e:
        raise Exception('_demo2 sub-error')


def _demo():
    try:
        _demo2()
    except Exception as e:
        print(f'### With reverse_chain=0')
        show(brief=1, reverse_chain=0)
        print(f'### With reverse_chain=1')
        show(brief=1, reverse_chain=1)

if __name__ == '__main__':
    if sys.argv[1:2] == ['--doctest']:
        # Support for running individual tests.
        import doctest
        if sys.argv[2:]:
            for ff in sys.argv[2:]:
                fff = globals()[ff]
                doctest.run_docstring_examples(fff, globals())
        else:
            doctest.testmod(None, verbose=0)
    elif sys.argv[1:] == ['demo']:
        _demo()
    else:
        assert 0, f'Unrecognised {sys.argv[1:]=}.'
