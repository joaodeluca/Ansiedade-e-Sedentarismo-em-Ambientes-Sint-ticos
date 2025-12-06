# Ansiedade-e-Sedentarismo-em-Ambientes-Sintéticos
Ansiedade e Sedentarismo em Ambientes Sintéticos: Um Estudo Experimental com Personas Geradas por LLMs
Este repositório contém o pipeline completo usado no TCC para gerar personas sintéticas, aplicar um estressor controlado e coletar respostas ao STAI-S (State-Trait Anxiety Inventory – State / forma Y-1), com calibração empírica a partir do dataset MMASH.

A lógica central do projeto é:

Calibrar sedentarismo e ansiedade usando humanos reais do MMASH (actigrafia + STAI-S real).

Gerar sedentarismo sintético (sed_ratio) seguindo a distribuição real observada no MMASH.

Gerar um STAI alvo sintético coerente com o sedentarismo, preservando a relação sedentarismo → ansiedade observada nos dados reais.

Passar sed_ratio + STAI alvo + cenário estressor para o LLM.

Receber como saída um JSON contendo os 20 itens do STAI-S (escala 1–4).

Calcular STAI total, validar consistência psicométrica e analisar estatisticamente os resultados.
