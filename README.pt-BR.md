# pdf_steg

Português · [English](README.md)

![pdf_steg](docs/hero.png)

> **Toolkit de esteganografia na camada de texto de PDFs.** Esconde mensagens
> em PDFs que renderizam idênticos ao original para um leitor humano, mas
> são extraíveis por software (`pdftotext`, `page.get_text()`, document
> loaders de LLM…). Útil para watermarking, teste de robustez de pipelines
> de ingestão por agentes de IA, CTFs e pesquisa em esteganografia.

![demo](docs/demo.gif)

Usa [PyMuPDF](https://pymupdf.readthedocs.io/).

## O que faz

Um PDF tem duas camadas que podem divergir: o que um humano enxerga (glifos
renderizados) e o que software extrai (camada de texto / objetos de caractere).
Esta ferramenta explora essa divergência.

Duas técnicas, dois subcomandos:

| Subcomando | Página visível                  | Conteúdo da camada de texto                         |
| ---------- | -------------------------------- | ---------------------------------------------------- |
| `hide`     | Idêntica ao original (rasterizada) | Apenas as letras escolhidas da mensagem secreta, nas posições originais |
| `embed`    | Idêntica ao original             | Texto original + payload `[STG:<base64>:STG]`, renderizado invisível |

Os dois geram PDFs visualmente idênticos ao original. A diferença está no que
`pdftotext` / `page.get_text()` / Ctrl+A devolvem.

## Por que existe

A capacidade é dual-use. Usos legítimos documentados:

- **Teste de segurança em agentes de IA próprios** — verificar se um pipeline
  de ingestão de documentos (RAG, sumarização, OCR) é influenciado por
  conteúdo invisível ao revisor humano. É a mesma ideia de pesquisa em
  prompt injection, aplicada a entradas em PDF.
- **Watermarking** — embutir uma string de atribuição/rastreio que sobrevive
  a copy-paste mas não polui o layout visível.
- **Pesquisa em esteganografia e CTFs** — ilustrar de forma limpa a divergência
  entre camada de imagem e camada de texto em PDFs.
- **Ensino** — mostrar como a extração de texto difere da renderização visual.

Fora do escopo: mirar sistemas de terceiros sem autorização, ou evadir
detecção em deployments adversariais. Use em infraestrutura própria ou em
testes autorizados.

## Instalação

```bash
pip install pymupdf
```

## Uso

### `analyze` — inventário de letras

```bash
python pdf_steg.py analyze entrada.pdf
```

Imprime quantos caracteres de cada tipo o PDF tem. Útil pra saber se a
mensagem secreta cabe na técnica `hide` (toda letra da mensagem precisa
aparecer pelo menos uma vez no documento).

### `hide` — rasterização seletiva

```bash
python pdf_steg.py hide entrada.pdf -m "minha mensagem" -o saida.pdf [--mode MODO] [--seed N] [--dpi N] [--strict]
```

Renderiza cada página como imagem e reinsere uma *camada de texto invisível*
(`render_mode=3`) contendo os caracteres de `--message`, cada um na posição
original que ocupava no PDF de entrada. No PDF resultante, copy-paste da
página inteira devolve só a mensagem secreta — o restante é imagem e não
é selecionável.

Por default a ferramenta tenta embutir **todos** os caracteres da mensagem —
letras, dígitos, pontuação e espaços. Se um caractere não-alfanumérico
(`@`, espaço, etc.) não puder ser inserido (sem ocorrência no PDF, ou
ordem inviável), ele é silenciosamente removido da mensagem embutida e
um aviso é impresso em stderr. Já alfanuméricos são essenciais — perder
uma letra corromperia a mensagem — então uma letra ausente é erro fatal.
Use `--strict` pra transformar **qualquer** char ausente em erro.

`--mode` controla como as posições são escolhidas entre as ocorrências
disponíveis:

| Modo     | Comportamento                                                     |
| -------- | ----------------------------------------------------------------- |
| `greedy` | Primeira ocorrência depois do cursor — caracteres concentram no início |
| `spread` | **Default.** Estratificado aleatório — cada caractere mira sua fatia do documento com jitter; quando a fatia está vazia, escolhe a próxima ocorrência à frente |
| `even`   | Centro determinístico de cada fatia — distribuição regular sem aleatoriedade |

Se a mensagem é minimamente viável (cada caractere essencial tem pelo menos
uma ocorrência em ordem), `spread` e `even` garantem inserção — nunca
falham depois de começar. `--seed N` torna o `spread` reprodutível.
`--dpi` controla a resolução da rasterização (default 220).

### `reveal` — lê um PDF gerado por `hide`

```bash
python pdf_steg.py reveal saida.pdf
```

Despeja a camada de texto duas vezes: como extraída (com as quebras de linha
naturais por causa de letras em linhas visuais diferentes) e uma versão
"compacta" sem nenhum espaço em branco — que é a mensagem.

### `embed` — payload em texto invisível

```bash
# default: mantém a camada de texto visível intacta
python pdf_steg.py embed entrada.pdf -m "mensagem secreta" -o saida.pdf

# também rasteriza o texto visível, deixando o payload como único texto extraível
python pdf_steg.py embed entrada.pdf -m "mensagem secreta" -o saida.pdf --rasterize [--dpi N]
```

Codifica a mensagem como `[STG:<base64>:STG]` e a adiciona à primeira página
como um text run de 1 pt invisível. A página renderiza idêntica ao original.

| Flag             | Página visível       | O que `get_text()` devolve                          |
| ---------------- | -------------------- | ---------------------------------------------------- |
| (nenhuma, default) | Idêntica à origem    | Texto original + `[STG:...:STG]`                     |
| `--rasterize`    | Idêntica à origem    | Apenas `[STG:...:STG]` (texto visível vira imagem)   |

A camada base64 garante que a mensagem aceita qualquer UTF-8 (acentos,
emoji, …) mesmo quando a fonte embutida não tem aqueles glifos.

### `extract` — lê um PDF gerado por `embed`

```bash
python pdf_steg.py extract saida.pdf
```

Procura o sentinela `[STG:...:STG]` no texto da página, decodifica o base64,
imprime o resultado.

## Limitações

- **O PDF de entrada precisa ter camada de texto extraível.** PDFs escaneados
  sem OCR não têm texto pra trabalhar — passe OCR antes.
- **`hide` exige que cada caractere essencial (alfanumérico) da mensagem
  exista na origem.** Acentos são normalizados (`á` casa com `a`).
  Caracteres não-alfanuméricos (espaços, pontuação, símbolos) são
  best-effort: a ferramenta tenta embuti-los mas omite com aviso no stderr
  se o PDF não tiver ocorrência. Use `--strict` para falhar duro nesses
  casos.
- **`embed` no modo default deixa o texto visível na camada de texto.** Quem
  fizer Ctrl+A no PDF renderizado verá `[STG:...:STG]` em algum ponto do
  clipboard. Use `--rasterize` para ocultação mais forte.
- **Sem criptografia.** O payload é base64, não cifrado. Se você precisa de
  confidencialidade além de obscuridade, criptografe a mensagem antes de
  passar pra ferramenta.

## Arquivos

- [`pdf_steg.py`](pdf_steg.py) — a CLI
- [`make_sample.py`](make_sample.py) — gera um PDF de teste pequeno
- `sample.pdf` / `big.pdf` — entradas de exemplo (depois de rodar `make_sample.py`)

## Licença

[MIT](LICENSE) © 2026 Marcelo Duchene
