"""
Contact header substitution — two-phase approach.

Phase 1  inject_placeholders(tex)
  Replace whatever contact values are in the template with neutral ASCII tokens
  so real PII is never sent to the OpenAI API.

Phase 2  restore_contact(tex, profile)
  Replace the placeholder tokens with real values from the applicant profile.
  Called on the tailored LaTeX *after* the API returns.

Handles two template styles:
  - Resume       : inline values inside the \\begin{center} block
  - Cover letter : \\newcommand{\\my...}{} declarations at the top
"""

import re

# Plain ASCII tokens — no LaTeX special characters
_NAME              = "CONTACTPH_NAME"
_PHONE             = "CONTACTPH_PHONE"
_EMAIL             = "CONTACTPH_EMAIL"
_LINKEDIN_URL      = "CONTACTPH_LINKEDIN_URL"
_LINKEDIN_DISPLAY  = "CONTACTPH_LINKEDIN_DISPLAY"
_GITHUB_URL        = "CONTACTPH_GITHUB_URL"
_GITHUB_DISPLAY    = "CONTACTPH_GITHUB_DISPLAY"
_PORTFOLIO_URL     = "CONTACTPH_PORTFOLIO_URL"
_PORTFOLIO_DISPLAY = "CONTACTPH_PORTFOLIO_DISPLAY"
_LINKEDIN_HANDLE   = "CONTACTPH_LINKEDIN_HANDLE"
_GITHUB_USER       = "CONTACTPH_GITHUB_USER"


# ── Phase 1 ───────────────────────────────────────────────────────────────────

def inject_placeholders(tex: str) -> str:
    """
    Replace contact header values in *tex* with placeholder tokens.
    Call this before passing templates to the OpenAI API.
    """
    if r"\newcommand{\myname}" in tex:
        return _inject_cover_letter(tex)
    return _inject_resume(tex)


def _inject_resume(tex: str) -> str:
    # {\huge\scshape\textbf{Jordan Park}}
    tex = re.sub(
        r'\{\\huge\\scshape\\textbf\{[^}]*\}\}',
        lambda _: '{\\huge\\scshape\\textbf{' + _NAME + '}}',
        tex,
    )
    # \faPhone\ 778-340-5621\enspace
    tex = re.sub(
        r'(\\faPhone\\ )([^\\]+?)(\\enspace)',
        lambda m: m.group(1) + _PHONE + m.group(3),
        tex,
    )
    # \faEnvelope\ \href{mailto:...}{...}
    tex = re.sub(
        r'\\faEnvelope\\ \\href\{mailto:[^}]+\}\{[^}]+\}',
        lambda _: f'\\faEnvelope\\ \\href{{mailto:{_EMAIL}}}{{{_EMAIL}}}',
        tex,
    )
    # \faLinkedin\ \href{...}{...}
    tex = re.sub(
        r'\\faLinkedin\\ \\href\{[^}]+\}\{[^}]+\}',
        lambda _: f'\\faLinkedin\\ \\href{{{_LINKEDIN_URL}}}{{{_LINKEDIN_DISPLAY}}}',
        tex,
    )
    # \faGithub\ \href{...}{...}
    tex = re.sub(
        r'\\faGithub\\ \\href\{[^}]+\}\{[^}]+\}',
        lambda _: f'\\faGithub\\ \\href{{{_GITHUB_URL}}}{{{_GITHUB_DISPLAY}}}',
        tex,
    )
    # \faBook\ \href{...}{...}%
    tex = re.sub(
        r'\\faBook\\ \\href\{[^}]+\}\{[^}]+\}%?',
        lambda _: f'\\faBook\\ \\href{{{_PORTFOLIO_URL}}}{{{_PORTFOLIO_DISPLAY}}}%',
        tex,
    )
    return tex


def _inject_cover_letter(tex: str) -> str:
    tex = re.sub(
        r'(\\newcommand\{\\myname\}\{)[^}]*(\})',
        lambda m: m.group(1) + _NAME + m.group(2),
        tex,
    )
    tex = re.sub(
        r'(\\newcommand\{\\myphone\}\{)[^}]*(\})',
        lambda m: m.group(1) + _PHONE + m.group(2),
        tex,
    )
    tex = re.sub(
        r'(\\newcommand\{\\myemail\}\{)[^}]*(\})',
        lambda m: m.group(1) + _EMAIL + m.group(2),
        tex,
    )
    tex = re.sub(
        r'(\\newcommand\{\\mylinkedin\}\{)[^}]*(\})',
        lambda m: m.group(1) + _LINKEDIN_HANDLE + m.group(2),
        tex,
    )
    tex = re.sub(
        r'(\\newcommand\{\\mygithub\}\{)[^}]*(\})',
        lambda m: m.group(1) + _GITHUB_USER + m.group(2),
        tex,
    )
    # Portfolio is also inline in the cover letter body
    tex = re.sub(
        r'\\faBook\\ \\href\{[^}]+\}\{[^}]+\}%?',
        lambda _: f'\\faBook\\ \\href{{{_PORTFOLIO_URL}}}{{{_PORTFOLIO_DISPLAY}}}%',
        tex,
    )
    return tex


# ── Phase 2 ───────────────────────────────────────────────────────────────────

def restore_contact(tex: str, profile: dict) -> str:
    """
    Replace placeholder tokens in *tex* with real values from *profile*.
    Call this on the tailored LaTeX returned by the OpenAI API.
    """
    linkedin  = profile.get("linkedin", "")
    github    = profile.get("github", "")
    portfolio = profile.get("portfolio", "")

    for placeholder, value in (
        (_NAME,              _escape_latex(profile.get("name", ""))),
        (_PHONE,             profile.get("phone", "")),
        (_EMAIL,             profile.get("email", "")),
        (_LINKEDIN_URL,      _full_url(linkedin)),
        (_LINKEDIN_DISPLAY,  linkedin),
        (_GITHUB_URL,        _full_url(github)),
        (_GITHUB_DISPLAY,    github),
        (_PORTFOLIO_URL,     _full_url(portfolio)),
        (_PORTFOLIO_DISPLAY, portfolio),
        (_LINKEDIN_HANDLE,   _strip_prefix(linkedin, ("https://linkedin.com/in/", "linkedin.com/in/"))),
        (_GITHUB_USER,       _strip_prefix(github, ("https://github.com/", "github.com/"))),
    ):
        tex = tex.replace(placeholder, value)

    # If portfolio is empty, remove the \faBook line entirely
    if not portfolio:
        tex = re.sub(r'[ \t]*\\faBook\\ \\href\{[^}]*\}\{[^}]*\}%?[ \t]*\n?', '', tex)

    return tex


# ── Utilities ─────────────────────────────────────────────────────────────────

def _full_url(value: str) -> str:
    if not value or value.startswith("http"):
        return value
    return f"https://{value}"


def _strip_prefix(value: str, prefixes: tuple) -> str:
    for prefix in prefixes:
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


def _escape_latex(text: str) -> str:
    for char, escaped in (
        ('\\', r'\textbackslash{}'),
        ('&',  r'\&'),
        ('%',  r'\%'),
        ('$',  r'\$'),
        ('#',  r'\#'),
        ('_',  r'\_'),
        ('{',  r'\{'),
        ('}',  r'\}'),
        ('~',  r'\textasciitilde{}'),
        ('^',  r'\textasciicircum{}'),
    ):
        text = text.replace(char, escaped)
    return text
