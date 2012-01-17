"""
Internal subroutines for e.g. aborting execution with an error message,
or performing indenting on multiline output.
"""

import sys
import textwrap

def abort(msg):
    """
    Abort execution, print ``msg`` to stderr and exit with error status (1.)

    This function currently makes use of `sys.exit`_, which raises
    `SystemExit`_. Therefore, it's possible to detect and recover from inner
    calls to `abort` by using ``except SystemExit`` or similar.

    .. _sys.exit: http://docs.python.org/library/sys.html#sys.exit
    .. _SystemExit: http://docs.python.org/library/exceptions.html#exceptions.SystemExit
    """
    from fabric.state import output
    if output.aborts:
        print >> sys.stderr, "\nFatal error: " + str(msg)
        print >> sys.stderr, "\nAborting."
    sys.exit(1)


def warn(msg):
    """
    Print warning message, but do not abort execution.

    This function honors Fabric's :doc:`output controls
    <../../usage/output_controls>` and will print the given ``msg`` to stderr,
    provided that the ``warnings`` output level (which is active by default) is
    turned on.
    """
    from fabric.state import output
    if output.warnings:
        print >> sys.stderr, "\nWarning: %s\n" % msg


def indent(text, spaces=4, strip=False):
    """
    Return ``text`` indented by the given number of spaces.

    If text is not a string, it is assumed to be a list of lines and will be
    joined by ``\\n`` prior to indenting.

    When ``strip`` is ``True``, a minimum amount of whitespace is removed from
    the left-hand side of the given string (so that relative indents are
    preserved, but otherwise things are left-stripped). This allows you to
    effectively "normalize" any previous indentation for some inputs.
    """
    # Normalize list of strings into a string for dedenting. "list" here means
    # "not a string" meaning "doesn't have splitlines". Meh.
    if not hasattr(text, 'splitlines'):
        text = '\n'.join(text)
    # Dedent if requested
    if strip:
        text = textwrap.dedent(text)
    prefix = ' ' * spaces
    output = '\n'.join(prefix + line for line in text.splitlines())
    # Strip out empty lines before/aft
    output = output.strip()
    # Reintroduce first indent (which just got stripped out)
    output = prefix + output
    return output


def puts(text, show_prefix=None, end="\n", flush=False):
    """
    An alias for ``print`` whose output is managed by Fabric's output controls.

    In other words, this function simply prints to ``sys.stdout``, but will
    hide its output if the ``user`` :doc:`output level
    </usage/output_controls>` is set to ``False``.

    If ``show_prefix=False``, `puts` will omit the leading ``[hostname]``
    which it tacks on by default. (It will also omit this prefix if
    ``env.host_string`` is empty.)

    Newlines may be disabled by setting ``end`` to the empty string (``''``).
    (This intentionally mirrors Python 3's ``print`` syntax.)

    You may force output flushing (e.g. to bypass output buffering) by setting
    ``flush=True``.

    .. versionadded:: 0.9.2
    .. seealso:: `~fabric.utils.fastprint`
    """
    from fabric.state import output, env
    if show_prefix is None:
        show_prefix = env.output_prefix
    if output.user:
        prefix = ""
        if env.host_string and show_prefix:
            prefix = "[%s] " % env.host_string
        sys.stdout.write(prefix + str(text) + end)
        if flush:
            sys.stdout.flush()


def fastprint(text, show_prefix=False, end="", flush=True):
    """
    Print ``text`` immediately, without any prefix or line ending.

    This function is simply an alias of `~fabric.utils.puts` with different
    default argument values, such that the ``text`` is printed without any
    embellishment and immediately flushed.

    It is useful for any situation where you wish to print text which might
    otherwise get buffered by Python's output buffering (such as within a
    processor intensive ``for`` loop). Since such use cases typically also
    require a lack of line endings (such as printing a series of dots to
    signify progress) it also omits the traditional newline by default.

    .. note::

        Since `~fabric.utils.fastprint` calls `~fabric.utils.puts`, it is
        likewise subject to the ``user`` :doc:`output level
        </usage/output_controls>`.

    .. versionadded:: 0.9.2
    .. seealso:: `~fabric.utils.puts`
    """
    return puts(text=text, show_prefix=show_prefix, end=end, flush=flush)


def handle_prompt_abort(prompt_for):
    import fabric.state
    reason = "Needed to prompt for %s, but %%s" % prompt_for
    # Explicit "don't prompt me bro"
    if fabric.state.env.abort_on_prompts:
        abort(reason % "abort-on-prompts was set to True")
    # Implicit "parallel == stdin/prompts have ambiguous target"
    if fabric.state.env.parallel:
        abort(reason % "input would be ambiguous in parallel mode")


class _AttributeDict(dict):
    """
    Dictionary subclass enabling attribute lookup/assignment of keys/values.

    For example::

        >>> m = _AttributeDict({'foo': 'bar'})
        >>> m.foo
        'bar'
        >>> m.foo = 'not bar'
        >>> m['foo']
        'not bar'

    ``_AttributeDict`` objects also provide ``.first()`` which acts like
    ``.get()`` but accepts multiple keys as arguments, and returns the value of
    the first hit, e.g.::

        >>> m = _AttributeDict({'foo': 'bar', 'biz': 'baz'})
        >>> m.first('wrong', 'incorrect', 'foo', 'biz')
        'bar'

    """
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            # to conform with __getattr__ spec
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

    def first(self, *names):
        for name in names:
            value = self.get(name)
            if value:
                return value


class _AliasDict(_AttributeDict):
    """
    `_AttributeDict` subclass that allows for "aliasing" of keys to other keys.

    Upon creation, takes an ``aliases`` mapping, which should map alias names
    to lists of key names. Aliases do not store their own value, but instead
    set (override) all mapped keys' values. For example, in the following
    `_AliasDict`, calling ``mydict['foo'] = True`` will set the values of
    ``mydict['bar']``, ``mydict['biz']`` and ``mydict['baz']`` all to True::

        mydict = _AliasDict(
            {'biz': True, 'baz': False},
            aliases={'foo': ['bar', 'biz', 'baz']}
        )

    Because it is possible for the aliased values to be in a heterogenous
    state, reading aliases is not supported -- only writing to them is allowed.
    This also means they will not show up in e.g. ``dict.keys()``.

    ..note::

        Aliases are recursive, so you may refer to an alias within the key list
        of another alias. Naturally, this means that you can end up with
        infinite loops if you're not careful.

    `_AliasDict` provides a special function, `expand_aliases`, which will take
    a list of keys as an argument and will return that list of keys with any
    aliases expanded. This function will **not** dedupe, so any aliases which
    overlap will result in duplicate keys in the resulting list.
    """
    def __init__(self, arg=None, aliases=None):
        init = super(_AliasDict, self).__init__
        if arg is not None:
            init(arg)
        else:
            init()
        # Can't use super() here because of _AttributeDict's setattr override
        dict.__setattr__(self, 'aliases', aliases)

    def __setitem__(self, key, value):
        # Attr test required to not blow up when deepcopy'd
        if hasattr(self, 'aliases') and key in self.aliases:
            for aliased in self.aliases[key]:
                self[aliased] = value
        else:
            return super(_AliasDict, self).__setitem__(key, value)

    def expand_aliases(self, keys):
        ret = []
        for key in keys:
            if key in self.aliases:
                ret.extend(self.expand_aliases(self.aliases[key]))
            else:
                ret.append(key)
        return ret


def error(message, func=None, exception=None, stdout=None, stderr=None):
    """
    Call ``func`` with given error ``message``.

    If ``func`` is None (the default), the value of ``env.warn_only``
    determines whether to call ``abort`` or ``warn``.

    If ``exception`` is given, it is inspected to get a string message, which
    is printed alongside the user-generated ``message``.

    If ``stdout`` and/or ``stderr`` are given, they are assumed to be strings
    to be printed.
    """
    import fabric.state
    if func is None:
        func = fabric.state.env.warn_only and warn or abort
    # If debug printing is on, append a traceback to the message
    if fabric.state.output.debug:
        message += "\n\n" + format_exc()
    # Otherwise, if we were given an exception, append its contents.
    elif exception is not None:
        # Figure out how to get a string out of the exception; EnvironmentError
        # subclasses, for example, "are" integers and .strerror is the string.
        # Others "are" strings themselves. May have to expand this further for
        # other error types.
        if hasattr(exception, 'strerror') and exception.strerror is not None:
            underlying = exception.strerror
        else:
            underlying = exception
        message += "\n\nUnderlying exception:\n" + indent(str(underlying))
    if func is abort:
        if stdout is not None and not output.stdout and stdout:
            message += _format_error_output("Standard output", stdout)
        if stderr is not None and not output.stderr and stderr:
            message += _format_error_output("Standard error", stderr)
    return func(message)


def _format_error_output(header, body):
    term_width = _pty_size()[1]
    header_side_length = (term_width - (len(header) + 2)) / 2
    mark = "="
    side = mark * header_side_length
    return "\n\n%s %s %s\n\n%s\n\n%s" % (
        side, header, side, body, mark * term_width
    )
