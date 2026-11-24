"""Gera o HTML autônomo da LP para o widget HTML do Elementor.

Lê index.html (CSS e JS embutidos) e escreve elementor/expert-elementor.html com tudo isolado dentro de #esn,
para não afetar o tema (e o tema não afetar a página). Unidades rem viram px, porque alguns temas mudam o
tamanho da fonte do <html> e isso encolheria a página inteira.

Uso: python elementor/gerar.py   (rodar na pasta expert-simples-nacional)
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.dirname(os.path.abspath(__file__))
SCOPE = '#esn'
PREFIX = 'esn-'


def read(name):
    with open(os.path.join(ROOT, name), encoding='utf-8') as f:
        return f.read().replace('\r\n', '\n')


# ------------------------------------------------------------------ CSS

def split_top(text, sep):
    """Divide por sep ignorando o que está dentro de parênteses e aspas."""
    parts, depth, quote, cur = [], 0, None, ''
    for ch in text:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in '"\'':
            quote = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append(cur)
            cur = ''
            continue
        cur += ch
    parts.append(cur)
    return parts


def scope_selector(sel):
    sel = sel.strip()
    if sel in (':root', 'body'):
        return SCOPE
    if sel.startswith('body'):
        return SCOPE + sel[4:]
    if sel.startswith('*'):
        return f'{SCOPE}, {SCOPE} {sel}' if sel == '*' else f'{SCOPE}{sel[1:]}, {SCOPE} {sel}'
    return f'{SCOPE} {sel}'


def parse_blocks(css):
    """Devolve [(prelude, body)] do nível atual."""
    out, i, n = [], 0, len(css)
    while i < n:
        j = css.find('{', i)
        if j == -1:
            break
        prelude = css[i:j].strip()
        depth, k, quote = 1, j + 1, None
        while k < n and depth:
            ch = css[k]
            if quote:
                if ch == quote:
                    quote = None
            elif ch in '"\'':
                quote = ch
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            k += 1
        out.append((prelude, css[j + 1:k - 1]))
        i = k
    return out


def scope_css(css, keyframes):
    res = []
    for prelude, body in parse_blocks(css):
        if prelude.startswith('@keyframes'):
            name = prelude.split()[1]
            res.append(f'@keyframes {keyframes[name]} {{{body}}}')
        elif prelude.startswith('@property'):
            res.append(f'{prelude} {{{body}}}')
        elif prelude.startswith('@media') or prelude.startswith('@supports'):
            res.append(f'{prelude} {{\n{scope_css(body, keyframes)}\n}}')
        elif prelude == 'html':
            # rolagem suave e compensação da barra fixa nos links internos (#oferta)
            res.append(f'html {{{body}}}')
        else:
            sels = ', '.join(scope_selector(s) for s in split_top(prelude, ','))
            res.append(f'{sels} {{{body}}}')
    return '\n'.join(res)


def rem_to_px(css):
    def repl(m):
        v = float(m.group(1)) * 16
        return (f'{v:.2f}'.rstrip('0').rstrip('.')) + 'px'
    return re.sub(r'(?<![\w.-])(\d*\.?\d+)rem\b', repl, css)


def build_css(css):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    css = rem_to_px(css)
    names = re.findall(r'@keyframes\s+([\w-]+)', css)
    keyframes = {n: PREFIX + n for n in names}

    def rename(m):
        value = m.group(2)
        for n in sorted(names, key=len, reverse=True):
            value = re.sub(rf'(?<![\w-]){re.escape(n)}(?![\w-])', keyframes[n], value)
        return m.group(1) + value
    css = re.sub(r'(animation(?:-name)?\s*:)([^;}]*)', rename, css)
    reset = (
        # desfaz estilos do tema nos elementos da página; as regras abaixo (mais específicas) redefinem tudo
        f'{SCOPE} :where(div, span, section, article, header, footer, main, nav, aside, figure, figcaption, '
        'h1, h2, h3, h4, h5, h6, p, a, ul, ol, li, blockquote, cite, mark, strong, b, em, i, s, small, '
        'button, details, summary, label, input) { all: revert; }\n'
        # img fica fora do revert para manter a proporção que vem de width/height
        f'{SCOPE} img {{ border: 0; border-radius: 0; box-shadow: none; opacity: 1; padding: 0; margin: 0; max-width: none; }}\n'
        f'{SCOPE} {{ position: relative; isolation: isolate; text-align: start; line-height: normal; }}\n'
    )
    return reset + scope_css(css, keyframes)


# ------------------------------------------------------------------ JS

def build_js(js):
    js = re.sub(r'\bdocument\.querySelector(All)?\(', r'root.querySelector\1(', js)
    assert 'documentElement' not in js and 'getElementById' not in js
    return ("(function(){\n  const root = document.getElementById('esn');\n  if (!root) return;\n"
            + js + "\n})();")


# ------------------------------------------------------------------ HTML

def main():
    html = read('index.html')
    css = html[html.index('<style>') + 7:html.index('</style>')]
    end = html.index('<script')
    body = html[html.index('<body>') + 6:end].strip()
    libs = '\n'.join(re.findall(r'<script src="[^"]+"></script>', html))
    js = '\n'.join(m for m in re.findall(r'<script>(.*?)</script>', html, flags=re.S))
    fonts = '\n'.join(re.findall(r'<link rel="preconnect"[^>]*>|<link href="https://fonts[^>]*>', html))
    page = (
        '<!-- Formação Expert em Simples Nacional — LP. Gerado por elementor/gerar.py; '
        'edite index.html e gere de novo. -->\n'
        f'{fonts}\n'
        f'<style>\n{build_css(css)}\n</style>\n\n'
        f'<div id="esn">\n{body}\n</div>\n\n'
        f'{libs}\n'
        f'<script>\n{build_js(js)}\n</script>\n'
    )
    dst = os.path.join(OUT, 'expert-elementor.html')
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write(page)
    print(f'expert-elementor.html: {len(page.encode()) // 1024} KB')


if __name__ == '__main__':
    main()
