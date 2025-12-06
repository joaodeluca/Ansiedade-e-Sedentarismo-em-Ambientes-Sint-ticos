# Ansiedade e Sedentarismo em Ambientes Sintéticos — Pipeline MMASH (TCC)

Este repositório contém o pipeline completo usado no TCC para **gerar personas sintéticas**, aplicar um **cenário estressor controlado** e coletar respostas ao **STAI-S (ansiedade de estado)**, com calibração empírica baseada no dataset **MMASH**.  
O MMASH **não é usado para treinar nenhum modelo** — ele entra apenas para **calibrar faixas e relações estatísticas reais** entre sedentarismo e ansiedade antes da geração sintética.

A lógica do trabalho é:

1. **Calibrar** sedentarismo e STAI-S com participantes reais do MMASH.  
2. **Gerar sed_ratio sintético** seguindo a distribuição humana do MMASH.  
3. **Gerar um STAI alvo sintético** coerente com o sed_ratio, preservando a dependência observada em humanos.  
4. **Enviar sed_ratio + STAI alvo + cenário estressor + questionário STAI-S** para a LLM.  
5. Receber **somente JSON** com os 20 itens do STAI-S (1–4).  
6. Validar, salvar e analisar estatisticamente.

---

## Estrutura do repositório

├── DataPaper/
├── analise_json/
├── saida_sintetico_one_situation/
├── analise_json_stai_mmash.ipynb
├── mmash_generate_one_situation_fast.py
└── prompts.py



---

## `prompts.py` — Itens do STAI-S

> **Importante:** este arquivo **só contém os 20 itens do STAI-S**, nada além disso.

Ele funciona como “molde” do questionário:  
- lista textual dos itens `stai_1` até `stai_20`  
- usados pelo script principal para montar o prompt final  
- a LLM responde esses itens em escala Likert **1 a 4**

Ou seja, o modelo **não inventa perguntas**: ele apenas preenche os itens oficiais do STAI-S.

---

## `mmash_generate_one_situation_fast.py` — Pipeline completo (calibração + geração + coleta)

Este é o **script central do projeto**. Ele concentra toda a lógica de calibração, geração de personas, construção do prompt, chamada à LLM e armazenamento dos resultados.

### O que o script faz (passo a passo)

#### 1) Localiza e lê o MMASH
- Procura a pasta `DataPaper/` (descompactando ZIP se necessário).
- Identifica as pastas `user_*` (cada uma é um participante real).

#### 2) Extrai as variáveis reais por participante
Para cada `user_*` válido:
- Lê `Actigraph.csv` e calcula o sedentarismo objetivo:

\[
sed\_ratio = \frac{\text{tempo sentado + tempo deitado}}{\text{tempo total monitorado}}
\]

- Lê `questionnaire.csv` e extrai o **STAI-S real**.
- Mantém somente participantes com **sed_ratio e STAI-S presentes**.

#### 3) Calibra os parâmetros empíricos
Com os participantes válidos, estima:
- **μ_sed, σ_sed** → distribuição humana de sedentarismo  
- **μ_stai, σ_stai** → distribuição humana de STAI-S  
- **r de Pearson(sed_ratio, STAI-S)**  
- **regressão linear** para preservar a dependência sedentarismo → ansiedade:

\[
STAI\_S = \alpha + \beta \cdot sed\_ratio
\]

Esses parâmetros são salvos em `mmash_stats.json` e controlam toda a simulação posterior.

#### 4) Gera personas sintéticas (sedentarismo)
Para cada persona:
- amostra sedentarismo sintético realista:

\[
sed\_ratio^{(sint)} \sim \mathcal{N}(\mu_{sed}, \sigma_{sed})
\]

- classifica lifestyle (ativo, moderado, muito ativo, sedentário) a partir de faixas de sed_ratio.

#### 5) Gera o STAI alvo sintético
Com o sed_ratio sintético, calcula o STAI alvo:

\[
STAI_{alvo} = \alpha + \beta \cdot sed\_ratio^{(sint)} + \varepsilon
\]

onde:
- **α** = ansiedade base esperada  
- **β** = aumento esperado de ansiedade conforme sedentarismo cresce  
- **ε** = ruído Normal (variabilidade humana realista, guiada por σ_stai e temperatura)

Depois:
- arredonda  
- **trunca em [20, 80]**, respeitando a escala psicométrica real do STAI-S.

#### 6) Monta o prompt final e chama a LLM
O script **monta internamente**:
- cenário estressor padronizado  
- instruções de saída em JSON  
- os itens do STAI-S (lidos de `prompts.py`)  
- os atributos da persona (sed_ratio, lifestyle, STAI alvo, temperatura)

A LLM deve retornar **apenas JSON** com:
- `stai_1` … `stai_20`  
- valores inteiros entre **1 e 4**  
- sem texto livre.

#### 7) Valida e salva incrementalmente
Cada JSON recebido passa por validação:
- contém 20 itens  
- todos entre 1 e 4  
- formato correto

Respostas válidas são salvas imediatamente para:
- evitar perda em caso de interrupção  
- manter rastreabilidade completa do experimento.

---

## `saida_sintetico_one_situation/` — Saídas brutas do experimento

Pasta gerada pelo script principal, contendo:
- lotes de respostas por temperatura  
- arquivos JSON/CSV com os 20 itens e STAI total  
- `mmash_stats.json` com os parâmetros calibrados

É a evidência experimental bruta.

---

## `analise_json/` — Bases tratadas para análise

Contém versões organizadas/limpas das saídas, normalmente com:
- dados concatenados
- STAI total calculado
- colunas auxiliares (temperatura, lifestyle, sed_ratio etc.)

---

## `analise_json_stai_mmash.ipynb` — Notebook de EDA e estatística

Notebook usado para:
1. carregar os resultados sintéticos  
2. validar novamente STAI total  
3. gerar estatísticas descritivas e tabelas  
4. comparar grupos (contraste principal: ativo vs sedentário)  
5. produzir tabelas finais usadas nos slides

---

## Como executar

### Requisitos
- Python 3.9+
- pandas, numpy, scipy, matplotlib, seaborn
- biblioteca de chamada ao modelo (já usada no script)

### Rodar o pipeline
Na raiz do repositório:
python mmash_generate_one_situation_fast.py

Isso executa:

- calibração MMASH
- geração de personas
- aplicação do cenário + STAI-S via LLM
- armazenamento das saídas.

Rodar a análise

Abra:
jupyter notebook analise_json_stai_mmash.ipynb


Observações finais

O MMASH é usado somente para calibração empírica.

O STAI-S aplicado é sempre o instrumento oficial de 20 itens.

Todo o controle experimental (cenário, prompt da LLM, validação e salvamento) está no script principal.
