class Doct:
    '''
    Behaves like a dict but also provides access with dot notation.
    
    >>> d = Doct()
    
    If we set with dict notation, we can read with dict and dot notation:
    >>> d['foo'] = 12
    >>> d['foo']
    12
    >>> d.foo
    12
    
    If we set with dot notation, we can read with dict and dot notation:
    >>> d.foo = 20
    >>> d.foo
    20
    >>> d['foo']
    20
    
    We get KeyError as with a dict:
    >>> try: d['bar']
    ... except KeyError as e: pass
    ... else: assert 0
    >>> try: d.bar
    ... except KeyError as e: pass
    ... else: assert 0
    
    Construction converts nested dict's into nested Doct's.
    >>> d = Doct(dict(foo=dict(bar=dict(qwerty=1))))
    >>> assert d.foo.bar.qwerty == 1
    >>> type(d.foo) == Doct
    True
    >>> type(d.foo.bar) == Doct
    True
    
    String representation works as expected.
    >>> str(d)
    "{'foo': {'bar': {'qwerty': 1}}}"
    >>> repr(d)
    "{'foo': {'bar': {'qwerty': 1}}}"
    
    Nested access works.
    >>> d.foo.bar.qwerty
    1
    >>> d['foo']['bar']['qwerty']
    1
    
    Assignment of nested dicts converts them into Dicts.
    >>> d.bbb = dict(ccc=dict(ddd=1))
    >>> type(d.bbb) == Doct
    True
    >>> type(d.bbb.ccc) == Doct
    True
    >>> d.bbb.ccc.ddd
    1
    
    We provide a `setdefault()` method.
    >>> d.setdefault('aaa', 42)
    42
    >>> d.aaa
    42
    
    >>> d.setpath('b', 'c', 'd', 100)
    >>> d.b.c.d
    100
    
    >>> d
    {'foo': {'bar': {'qwerty': 1}}, 'bbb': {'ccc': {'ddd': 1}}, 'aaa': 42, 'b': {'c': {'d': 100}}}
    >>> del d.b
    >>> d
    {'foo': {'bar': {'qwerty': 1}}, 'bbb': {'ccc': {'ddd': 1}}, 'aaa': 42}
    
    {'foo': {'bar': 1}}
    
    We can still use `_dict` as a key, even though it's a member of the class.
    >>> d = Doct(autopath=1)
    >>> d._dict = dict()
    >>> d
    {'_dict': {}}
    >>> d.foo.bar = 34
    >>> d
    {'_dict': {}, 'foo': {'bar': 34}}
    
    import difflib
    
    '''
    def __init__(self, *args, autopath=None, **kwargs):
        '''
        If <autopath> is true, reading non-existant keys will automatically
        set the key to a Doct().
        
        >>> d = Doct(autopath=1)
        >>> d.foo.bar = 1
        >>> d
        {'foo': {'bar': 1}}
        >>> d = Doct(autopath=1)
        >>> d['foo']['bar'] = 1
        >>> d
        {'foo': {'bar': 1}}
        '''
        super.__setattr__(self, '_dict', dict(*args, **kwargs))
        super.__setattr__(self, '_autopath', autopath)
        # Recursively convert dict items into Doct's.
        for key, value in self._dict.items():
            self._dict[key] = self._convert(value)
            #if isinstance(value, dict) and not isinstance(value, Doct):
            #    self._dict[key] = Doct(value)
    
    def __getattr__(self, key):
        if self._autopath:
            return self._dict.setdefault(key, Doct())
        return self._dict[key]
    
    def __setattr__(self, key, value):
        self._dict[key] = self._convert(value)
    
    def __getitem__(self, key):
        if self._autopath:
            return self._dict.setdefault(key, Doct())
        return self._dict[key]
    
    def __setitem__(self, key, value):
        self._dict[key] = self._convert(value)
    
    def __delattr__(self, key):
        del self._dict[key]
    
    def __str__(self):
        return str(self._dict)
    
    def __repr__(self):
        return repr(self._dict)
    
    def __len__(self):
        return len(self._dict)
    
    def __contains__(self, key):
        '''
        >>> d = Doct()
        >>> 'foo' in d
        False
        >>> d.foo = 12
        >>> 'foo' in d
        True
        '''
        return key in self._dict
    
    def _convert(self, value):
        if isinstance(value, dict) and not isinstance(value, Doct):
            value = Doct(value)
        return value
    
    def clear(self):
        self._dict.clear()
    
    def copy(self):
        return self._dict.copy()
    
    def popitem(self, *args, **kwargs):
        return self._dict.popitem(*args, **kwargs)
    
    def pop(self, *args, **kwargs):
        return self._dict.pop(*args, **kwargs)
    
    def update(self, *args, **kwargs):
        return self._dict.update(*args, **kwargs)
    
    def values(self, *args, **kwargs):
        return self._dict.values(*args, **kwargs)
    
    def setdefault(self, key, value):
        return self._dict.setdefault(key, self._convert(value))
    
    def setpath(self, *path):
        '''
        Convenience method for nested setting.
        
        >>> d = Doct()
        >>> d.setpath(1, 2, 3, 4)
        >>> d
        {1: {2: {3: 4}}}
        '''
        d = self
        for p in path[:-2]:
            d = d.setdefault(p, Doct())
        d[path[-2]] = path[-1]
    
    def setpathdefault(self, *path):
        '''
        Like setpath() but does not set final item if already present, and
        returns the final item.
        
        >>> d = Doct()
        >>> d.setpath(1, 2, 3, 4)
        >>> d
        {1: {2: {3: 4}}}
        >>> d.setpathdefault(1, 2, 3, 5)
        4
        >>> d
        {1: {2: {3: 4}}}
        '''
        d = self
        for p in path[:-2]:
            d = d.setdefault(p, Doct())
        d = d.setdefault(path[-2], path[-1])
        return d
    
    def get(self, key, default=None):
        return self._dict.get(key, default)
    
    def keys(self):
        return self._dict.keys()

def _check_members():
    import difflib
    def get(c):
        return sorted([i for i in dir(c) if not i.startswith('_')])
    dict_members = get(dict())
    doct_members = get(Doct())
    lines = difflib.unified_diff(dict_members, doct_members, lineterm='')
    print('\n'.join(lines))

#_check_members()
    
