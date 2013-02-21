"""
editor script for X/84, https://github.com/jquast/x84
"""
# This is probably the fourth or more ansi multi-line editor
# I've written for python. I did the least-effort this time.
# There isn't any actual multi-line editor, just this script
# that drives a LineEditor and a Lightbar.

WHITESPACE = u' '
SOFTWRAP=u'\n'
HARDWRAP=u'\r\n'

def get_help():
    import os
    return open(os.path.join(os.path.dirname(__file__), 'editor.txt')).read()

def wrap_rstrip(value):
    if value[-len(HARDWRAP):] == HARDWRAP:
        value = value[:-len(HARDWRAP)]
    if value[-len(SOFTWRAP):] == SOFTWRAP:
        value = value[:-len(SOFTWRAP)]
    return value

def softwrap_join(value):
    return WHITESPACE.join(value.split(SOFTWRAP))

def is_hardwrapped(ucs):
    return ucs[-(len(HARDWRAP)):] == HARDWRAP

def is_softwrapped(ucs):
    return ucs[-(len(SOFTWRAP)):] == SOFTWRAP

def get_lbcontent(lightbar):
    """
    Returns ucs string for content of Lightbar instance, ``lightbar``.
    """
    from x84.bbs import Ansi
    # a custom 'soft newline' versus 'hard newline' is implemented,
    # '\n' == 'soft', '\r\n' == 'hard'
    lines = list()
    for lno, (_row, ucs) in enumerate(lightbar.content):
        # first line always appends as-is, otherwise if the previous line
        # matched a hardwrap, or did not match softwrap, then append as-is.
        # (a simple .endswith() can't wll work with a scheme of '\n' vs.
        # '\r\n')
        if lno == 0 or (
                is_hardwrapped(lines[-1]) or not is_softwrapped(lines[-1])):
            lines.append(ucs)
        else:
            # otherwise the most recently appended line must end with
            # SOFTWRAP, strip that softwrap and re-assign value to a
            # whitespace-joined value by current line value.
            lines[-1] = WHITESPACE.join((lines[-1].rstrip(), ucs.lstrip(),))
    retval = Ansi(u''.join(lines)).encode_pipe()
    return retval


def set_lbcontent(lightbar, ucs):
    """
    Sets content of Lightbar instance, ``lightbar`` for given
    Unicode string, ``ucs``.
    """
    from x84.bbs import Ansi
    # a custom 'soft newline' versus 'hard newline' is implemented,
    # '\n' == 'soft', '\r\n' == 'hard'
    content = dict()
    lno = 0
    lines = ucs.split(HARDWRAP)
    for idx, ucs_line in enumerate(lines):
        if idx == len(lines) - 1 and 0 == len(ucs_line):
            continue
        ucs_joined = WHITESPACE.join(ucs_line.split(SOFTWRAP))
        ucs_wrapped = Ansi(ucs_joined).wrap(
                lightbar.visible_width).splitlines()
        for inner_lno, inner_line in enumerate(ucs_wrapped):
            content[lno] = u''.join((inner_line,
                SOFTWRAP if inner_lno != len(ucs_wrapped) - 1 else u''))
            lno += 1
        if 0 == len(ucs_wrapped):
            content[lno] = HARDWRAP
            lno += 1
        else:
            content[lno - 1] += HARDWRAP
    if 0 == len(content):
        content[0] = HARDWRAP
    lightbar.update(sorted(content.items()))


def yes_no(lightbar, msg, prompt_msg='are you sure?'):
    """ Prompt user for yes/no, returns True for yes, False for no. """
    from x84.bbs import Selector, echo, getch, getterminal
    term = getterminal()
    keyset = {
        'yes': (u'y', u'Y'),
        'no': (u'n', u'N'),
    }
    echo(u''.join((
        lightbar.border(),
        lightbar.pos(lightbar.height, lightbar.xpadding),
        msg, u' ', prompt_msg,)))
    sel = Selector(yloc=lightbar.yloc + lightbar.height - 1,
                  xloc=term.width - 28, width=12,
                  left='Yes', right='No')
    sel.colors['selected'] = term.reverse_red
    sel.keyset['left'].extend(keyset['yes'])
    sel.keyset['right'].extend(keyset['no'])
    echo(sel.refresh())
    while True:
        inp = getch()
        echo(sel.process_keystroke(inp))
        if((sel.selected and sel.selection == sel.left)
                or inp in keyset['yes']):
            # selected 'yes',
            return True
        elif((sel.selected or sel.quit)
                or inp in keyset['no']):
            # selected 'no'
            return False

def get_lightbar(ucs):
    """
    Returns lightbar instance with content of given
    Unicode string, ``ucs``.
    """
    from x84.bbs import getterminal, Lightbar
    term = getterminal()
    width = min(80, max(term.width, 40))
    yloc = 0
    height = term.height - yloc
    xloc = max(0, (term.width / 2) - (width / 2))
    lightbar = Lightbar(height, width, yloc, xloc)
    lightbar.glyphs['left-vert'] = lightbar.glyphs['right-vert'] = u''
    lightbar.colors['highlight'] = term.yellow_reverse
    set_lbcontent(lightbar, ucs)
    return lightbar

def get_lneditor(lightbar):
    """
    Returns ScrollingEditor instance positioned at location of current
    selection in Lightbar instance, ``lightbar``.
    """
    from x84.bbs import getterminal, ScrollingEditor
    term = getterminal()
    width = min(80, max(term.width, 40))
    yloc = (lightbar.yloc + lightbar.ypadding + lightbar.position[0] - 1)
    xloc = max(0, (term.width / 2) - (width / 2))
    lneditor = ScrollingEditor(width, yloc, xloc)
    lneditor.enable_scrolling = True
    lneditor.max_length = 65534
    lneditor.glyphs['bot-horiz'] = u''
    lneditor.glyphs['top-horiz'] = u''
    lneditor.colors['highlight'] = term.red_reverse
    lneditor.colors['border'] = term.bold_red
    # converts u'xxxxxx\r\n' to 'xxxxxx',
    # or 'zzzz\nxxxxxx\n' to u'zzzz xxxxxx',
    lneditor.update(softwrap_join(wrap_rstrip(lightbar.selection[1])))
    return lneditor


def main(save_key=u'draft'):
    """ Main procedure. """
    # pylint: disable=R0914,R0912,R0915
    #         Too many local variables
    #         Too many branches
    #         Too many statements
    from x84.bbs import getsession, getterminal, echo, getch, Ansi, Pager
    session, term = getsession(), getterminal()

    movement = (term.KEY_UP, term.KEY_DOWN, term.KEY_NPAGE,
                term.KEY_PPAGE, term.KEY_HOME, term.KEY_END,
                u'\r', term.KEY_ENTER)
    keyset = {'edit': (term.KEY_ENTER,),
              'command': (unichr(27), term.KEY_ESCAPE),
              'kill': (u'K',),
              'join': (u'J',),
              'rubout': (unichr(8), unichr(127),
                  unichr(23), term.KEY_BACKSPACE,),
            }

    def merge(newline=HARDWRAP):
        """
        Merges line editor content as a replacement for the currently
        selected lightbar row. Returns True if text inserted caused
        additional rows to be appended, which is meaningful in a window
        refresh context.
        """
        # merge line editor with pager window content. strange thing, we
        # edit u'\r\n' to become u'\r\nHello world.', and move newlines to
        # the right-most sideu, u'Hello world.\r\n'. This is just hackwork.
        lightbar.content[lightbar.index] = [
                lightbar.selection[0],
                softwrap_join(wrap_rstrip(lneditor.content))
                + HARDWRAP]
        prior_length = len(lightbar.content)
        prior_position = lightbar.position
        set_lbcontent(lightbar, get_lbcontent(lightbar))
        if len(lightbar.content) - prior_length == 0:
            echo(lightbar.refresh_row(prior_position[0]))
            return False
        while len(lightbar.content) - prior_length > 0:
            # hidden move-down for each appended line
            lightbar.move_down()
            prior_length += 1
        return True

    def statusline(lightbar):
        """
        Display status line and command help on ``lightbar`` borders
        """
        lightbar.colors['border'] = term.red if edit else term.yellow
        keyset_cmd = u''
        if not edit:
            keyset_cmd = u''.join((
                term.yellow(u'-( '),
                term.yellow_underline(u'S'), u':', term.bold(u'ave'),
                u' ',
                term.yellow_underline(u'A'), u':', term.bold(u'bort'),
                u' ',
                term.yellow_underline(u'?'), u':', term.bold(u'help'),
                term.yellow(u' )-'),))
#                    ) + keyset_cmd
            keyset_cmd = lightbar.pos(lightbar.height - 1,
                    max(0, lightbar.width - (len(Ansi(keyset_cmd)) + 3))
                    ) + keyset_cmd
        return u''.join((
            lightbar.border(),
            keyset_cmd,
            lightbar.pos(lightbar.height, lightbar.xpadding),
            u''.join((
                term.red(u'-[ '),
                u'EditiNG liNE ',
                term.reverse_red('%d' % (lightbar.index + 1,)),
                term.red(u' ]-'),)) if edit else u''.join((
                    term.yellow(u'-( '),
                    u'liNE ',
                    term.yellow('%d/%d ' % (
                        lightbar.index + 1,
                        len(lightbar.content),)),
                    '%d%% ' % (
                        int((float(lightbar.index + 1)
                            / max(1, len(lightbar.content))) * 100)),
                    term.yellow(u' )-'),)),
                lightbar.title(u''.join((
                        term.red('-] '),
                        term.bold(u'Escape'),
                        u':', term.bold_red(u'command mode'),
                        term.red(' [-'),)
                        ) if edit else u''.join((
                            term.yellow('-( '),
                            term.bold(u'Enter'),
                            u':', term.bold_yellow(u'edit mode'),
                            term.yellow(' )-'),))),))


    def redraw_lneditor(lightbar, lneditor):
        """
        Return ucs suitable for refreshing line editor.
        """
        return ''.join((
            term.normal,
            statusline(lightbar),
            lneditor.border(),
            lneditor.refresh()))


    def get_ui(ucs, lightbar=None):
        """
        Returns Lightbar and ScrollingEditor instance.
        """
        lbr = get_lightbar(ucs)
        lbr.position = (lightbar.position
                if lightbar is not None else (0, 0))
        lne = get_lneditor(lbr)
        return lbr, lne

    def banner():
        """
        Returns string suitable clearing screen
        """
        return u''.join((
            term.move(0, 0),
            term.normal,
            term.clear))

    def redraw(lightbar, lneditor):
        """
        Returns ucs suitable for redrawing Lightbar
        and ScrollingEditor UI elements.
        """
        return u''.join((
            term.normal,
            redraw_lightbar(lightbar),
            redraw_lneditor(lightbar, lneditor) if edit else u'',
            ))

    def redraw_lightbar(lightbar):
        """ Returns ucs suitable for redrawing Lightbar. """
        return u''.join((
            statusline(lightbar),
            lightbar.refresh(),))

    def resize(lightbar):
        """ Resize Lightbar. """
        if edit:
            # always re-merge current line on resize,
            merge()
        lbr, lne = get_ui(get_lbcontent(lightbar), lightbar)
        echo(redraw(lbr, lne))
        return lbr, lne

    ucs = session.user.get(save_key, u'')
    lightbar, lneditor = get_ui(ucs, None)
    echo(banner())
    dirty = True
    edit = False
    while True:
        # poll for refresh
        if session.poll_event('refresh'):
            echo(banner())
            lightbar, lneditor = resize(lightbar)
            dirty = True
        if dirty:
            session.activity = 'editing %s' % (save_key,)
            echo(redraw(lightbar, lneditor))
            dirty = False
        # poll for input
        inp = getch(1)

        # toggle edit mode,
        if inp in keyset['command'] or not edit and inp in keyset['edit']:
            edit = not edit  # toggle
            if not edit:
                # switched to command mode, merge our lines
                echo(term.normal + lneditor.erase_border())
                merge()
                lightbar.colors['highlight'] = term.yellow_reverse
            else:
                # switched to edit mode, instantiate new line editor
                lneditor = get_lneditor(lightbar)
                lightbar.colors['highlight'] = term.red_reverse
            dirty = True

        # edit mode, kill line
        elif not edit and inp in keyset['kill']:
            # when 'killing' a line, make accomidations to clear
            # bottom-most row, otherwise a ghosting effect occurs
            del lightbar.content[lightbar.index]
            set_lbcontent(lightbar, get_lbcontent(lightbar))
            if lightbar.visible_bottom > len(lightbar.content):
                echo(lightbar.refresh_row(lightbar.visible_bottom + 1))
            else:
                dirty = True

        # edit mode, join line
        elif (not edit and inp in keyset['join']
                and lightbar.index + 1 < len(lightbar.content)):
            idx = lightbar.index
            lightbar.content[idx] = (idx,
                    WHITESPACE.join((
                        lightbar.content[idx][1].rstrip(),
                        lightbar.content[idx + 1][1].lstrip(),)))
            del lightbar.content[idx + 1]
            prior_length = len(lightbar.content)
            set_lbcontent(lightbar, get_lbcontent(lightbar))
            if len(lightbar.content) - prior_length > 0:
                lightbar.move_down()
            dirty = True


        # command mode, basic cmds & movement
        elif not edit and inp is not None:
            if inp in (u'a', u'A',):
                if yes_no(lightbar, u'- AbORt -'):
                    return False
                dirty = True
            elif inp in (u's', u'S',):
                if yes_no(lightbar, u'- SAVE -'):
                    session.user[save_key] = HARDWRAP.join(
                            [softwrap_join(_ucs) for _ucs in
                                get_lbcontent(lightbar).split(HARDWRAP)])
                    return True
                dirty = True
            elif inp in (u'?',):
                pager = Pager(lightbar.height, lightbar.width,
                        lightbar.yloc, lightbar.xloc)
                pager.update(get_help())
                pager.colors['border'] = term.bold_blue
                echo(pager.border() + pager.title(u''.join((
                    term.blue(u'-( '),
                    term.blue_underline(u'r'), u':', term.bold(u'eturn'),
                    u' ',
                    term.blue(u' )-'),))))
                pager.keyset['exit'].extend([u'r', u'R'])
                pager.read()
                dirty = True
            else:
                echo(lightbar.process_keystroke(inp))
                if lightbar.moved:
                    echo(statusline(lightbar))

        # edit mode
        elif edit and inp in movement:
            merge()
            if inp in (u'\r', term.KEY_ENTER,):
                lightbar.content.insert(lightbar.index + 1,
                        [lightbar.selection[0] + 1, HARDWRAP])
                inp = term.KEY_DOWN
            lightbar.process_keystroke(inp)
            if lightbar.moved:
                echo(term.normal + lneditor.erase_border())
                lneditor = get_lneditor(lightbar)
            dirty = True

        # edit mode -- append character / backspace
        elif edit and inp is not None:
            if (inp in keyset['rubout']
                    and len(lneditor.content) == 0
                    and lightbar.index > 0):
                # erase past margin,
                echo(term.normal + lneditor.erase_border())
                del lightbar.content[lightbar.index]
                lightbar.move_up()
                set_lbcontent(lightbar, get_lbcontent(lightbar))
                lneditor = get_lneditor(lightbar)
                dirty = True
            else:
                # edit mode, add/delete ch
                echo(lneditor.process_keystroke(inp))
                if lneditor.moved:
                    echo(statusline(lightbar))
