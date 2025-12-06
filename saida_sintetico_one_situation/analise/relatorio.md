# Relatório de Análise — STAI-S (MMASH + LLM)

## Registros carregados (pós-limpeza)

| index | n | stai_mean | stai_sd | stai_min | stai_max |
| --- | --- | --- | --- | --- | --- |
| ALL | 9184 | 49.99836672473867 | 3.047823392392936 | 39 | 64 |

## Limpeza por temperatura

| temperature | rows_before | na_rows | out_of_range_rows | dropped |
| --- | --- | --- | --- | --- |
| 0.6 | 3184.0 | 0.0 | 0.0 | 0.0 |
| 0.75 | 3000.0 | 0.0 | 0.0 | 0.0 |
| 0.9 | 3000.0 | 0.0 | 0.0 | 0.0 |

## Resumo por temperatura

| index | n | stai_mean | stai_sd | stai_min | stai_max |
| --- | --- | --- | --- | --- | --- |
| temp=0.6 | 3184 | 50.045540201005025 | 3.318206171932592 | 39 | 64 |
| temp=0.75 | 3000 | 49.93233333333333 | 2.793866458062026 | 39 | 61 |
| temp=0.9 | 3000 | 50.01433333333333 | 2.9908376071071214 | 40 | 62 |

## Resumo por temperatura × lifestyle

| temperature | lifestyle | n | stai_mean | stai_sd | stai_min | stai_max |
| --- | --- | --- | --- | --- | --- | --- |
| 0.6 | ativo | 434 | 50.17741935483871 | 3.740835980495971 | 39 | 60 |
| 0.6 | moderado | 2405 | 49.99376299376299 | 3.168119744294299 | 39 | 64 |
| 0.6 | muito ativo | 13 | 51.15384615384615 | 3.1844977062365176 | 46 | 57 |
| 0.6 | sedentário | 332 | 50.204819277108435 | 3.7674357155184253 | 41 | 64 |
| 0.75 | ativo | 413 | 49.937046004842614 | 3.2352590254059486 | 39 | 60 |
| 0.75 | moderado | 2243 | 49.843067320552834 | 2.6045283848365974 | 40 | 61 |
| 0.75 | muito ativo | 12 | 52.5 | 3.68041499636312 | 48 | 59 |
| 0.75 | sedentário | 332 | 50.43674698795181 | 3.2784528104048296 | 43 | 61 |
| 0.9 | ativo | 393 | 50.038167938931295 | 3.2804412194358163 | 42 | 59 |
| 0.9 | moderado | 2273 | 49.96480422349318 | 2.874669633336538 | 40 | 61 |
| 0.9 | muito ativo | 10 | 50.3 | 4.547282460742656 | 42 | 58 |
| 0.9 | sedentário | 324 | 50.324074074074076 | 3.342646947209814 | 41 | 62 |

## Alfa de Cronbach por temperatura

| temperature | cronbach_alpha |
| --- | --- |
| 0.6 | 0.45170321275723874 |
| 0.75 | 0.44726165145054503 |
| 0.9 | 0.4254720969871602 |

## Correlações

| temperature | var | rho | p |
| --- | --- | --- | --- |
| 0.6 | lifestyle(Spearman) | -0.014952178427198658 | 0.39899270150523813 |
| 0.6 | sed_ratio(Pearson) | 0.002867330357558838 | 0.8715173043001124 |
| 0.6 | sed_ratio(Spearman) | -0.010334457361568555 | 0.5599414774162694 |
| 0.75 | lifestyle(Spearman) | 0.019990781641787178 | 0.2736948669012732 |
| 0.75 | sed_ratio(Pearson) | 0.024512200566284593 | 0.17952121838934762 |
| 0.75 | sed_ratio(Spearman) | 0.01809274386060155 | 0.3218572524285363 |
| 0.9 | lifestyle(Spearman) | 0.016311723278010892 | 0.3717945414556021 |
| 0.9 | sed_ratio(Pearson) | 0.02337446417191356 | 0.20057558081438984 |
| 0.9 | sed_ratio(Spearman) | 0.020118020357555385 | 0.2706523035024211 |

## Observações

- Linhas com itens fora de 1..4 ou com NaN foram removidas (sem imputação).
- Figuras em `./saida_sintetico_one_situation2/analise/figs/`.
- Tabelas em `./saida_sintetico_one_situation2/analise/tabelas/`.
