# Ansiedade-e-Sedentarismo-em-Ambientes-Sintéticos
Ansiedade e Sedentarismo em Ambientes Sintéticos: Um Estudo Experimental com Personas Geradas por LLMs
Este repositório contém o pipeline completo usado no TCC para gerar personas sintéticas, aplicar um estressor controlado e coletar respostas ao STAI-S (State-Trait Anxiety Inventory – State / forma Y-1), com calibração empírica a partir do dataset MMASH.

A lógica central do projeto é:

1.Calibrar sedentarismo e ansiedade usando humanos reais do MMASH (actigrafia + STAI-S real).

2.Gerar sedentarismo sintético (sed_ratio) seguindo a distribuição real observada no MMASH.

3.Gerar um STAI alvo sintético coerente com o sedentarismo, preservando a relação sedentarismo → ansiedade observada nos dados reais.

4.Passar sed_ratio + STAI alvo + cenário estressor para o LLM.

5.Receber como saída um JSON contendo os 20 itens do STAI-S (escala 1–4).

6.Calcular STAI total, validar consistência psicométrica e analisar estatisticamente os resultados.



1. DataPaper/ (Dataset MMASH)

Pasta do MMASH utilizada na calibração.
A estrutura é:

DataPaper/
  user_1/
    Actigraph.csv
    questionnaire.csv
    RR.csv
    sleep.csv
    ...
  user_2/
    ...
    
Cada user_* representa um participante humano monitorado por 24h.

O pipeline usa apenas:
Actigraph.csv → sedentarismo objetivo
questionnaire.csv → STAI-S real (ansiedade de estado)
Os demais arquivos (RR, sleep, saliva etc.) podem existir na base, mas não são obrigatórios para a calibração central do TCC.


3. mmash_generate_one_situation_fast.py (Pipeline principal)

Este é o script central do projeto.
Ele executa tudo de ponta a ponta, desde a calibração até salvar as respostas sintéticas.

3.1. O que o script faz passo a passo
(1) Localiza o MMASH

Descompacta ZIP do dataset (se necessário).

Encontra a pasta DataPaper/.

(2) Varre participantes reais

Para cada user_*:

Lê Actigraph.csv

Calcula sedentarismo real:

Lê questionnaire.csv

Extrai STAI-S real.

Mantém apenas participantes com sed_ratio e STAI-S presentes.

(3) Calibra parâmetros do MMASH

Com os participantes válidos o script calcula:

μ_sed, σ_sed → distribuição real de sedentarismo

μ_stai, σ_stai → distribuição real de STAI-S

r de Pearson(sed_ratio, STAI-S)

regressão linear STAI ~ sed_ratio (α, β):
STAI=α+β⋅sed_ratio

Esses parâmetros são salvos posteriormente em JSON para controlar a simulação.

(4) Geração de personas sintéticas

Para cada persona:
Atribui lifestyle (ativo, moderado, muito ativo, sedentário) conforme faixas de sed_ratio.

(5) Geração do STAI alvo sintético

Com sed_ratio sintético, calcula ansiedade alvo onde:

α = ansiedade base prevista

β = quanto a ansiedade aumenta com sedentarismo

ε = ruído Normal (variabilidade humana realista)

Depois:

arredonda

trunca em [20, 80], porque essa é a faixa do STAI-S real.

(6) Prompt para o LLM

Para cada persona, o modelo recebe:

-sed_ratio
-lifestyle
-STAI_alvo
-cenário estressor
-STAI-S completo (do prompts.py)
-instrução de retorno JSON.

(7) Coleta e validação de resposta

O script valida:

tem 20 itens

todos de 1 a 4

JSON válido

sem texto extra

Se falhar, reenvia a persona individualmente.

(8) Armazenamento incremental

Cada persona validada é salva imediatamente:

garante recuperação se cair no meio

garante rastreabilidade total.

4. saida_sintetico_one_situation/ (Saídas brutas)

Pasta onde ficam os resultados do script principal.

Tipicamente contém:

arquivos .json ou .csv por temperatura

lotes de personas por condição

métricas agregadas

o arquivo mmash_stats.json (parâmetros calibrados)

Essa pasta é a evidência experimental bruta.

5. analise_json/ (Dados organizados para análise)

Pasta com versões já tratadas/limpas das saídas sintéticas.

Em geral contém:

bases concatenadas

STAI total calculado

colunas auxiliares (temperatura, lifestyle, sed_ratio etc.)

É a entrada direta do notebook de análise.

6. analise_json_stai_mmash.ipynb (Notebook de EDA e estatística)

Notebook responsável por:

Carregar dados sintéticos organizados (analise_json/ ou saida_sintetico_one_situation/).

Recalcular/checar stai_total a partir dos 20 itens.

Fazer EDA (estatística descritiva, distribuição, consistência).

Comparar grupos (ativo vs sedentário como contraste principal).

Gerar tabelas finais usadas nos slides.

Esse notebook é o que produz:

médias por lifestyle e temperatura

contagens (n)

tabelas compactas para apresentação

testes estatísticos (ex.: t-test / Mann-Whitney quando necessário)
