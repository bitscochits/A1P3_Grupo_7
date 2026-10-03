# QA final estructural del conjunto

Generado por `python semana06/verificar_semana06.py --salida` el 2026-10-02 21:24, sobre el commit `19510a0` con cambios sin commitear, en 18 s. No se edita a mano.

Modelo: `data/modelo/conjunto.json` (558 nodos, 937 elementos). Anexo: semana04/exportar_unity.construir_anexo('conjunto') en memoria (el de disco era lt2).

| Prueba | Estado | Número | Criterio | Comando |
|---|---|---|---|---|
| Equilibrio G | **OK** | error 8.6e-05 kN de 97885.36 kN (cota 4.2e-03) | \|aplicada + reaccion\| <= apoyos que cuentan x 0.5e-4 kN | `python semana06/verificar_semana06.py` |
| Equilibrio Q | **OK** | error 9.0e-05 kN de 20509.63 kN (cota 4.2e-03) | \|aplicada + reaccion\| <= apoyos que cuentan x 0.5e-4 kN | `python semana06/verificar_semana06.py` |
| Corte basal EX | **OK** | V = 10814.02 kN = 0.10 W; error 5.9e-06 kN (cota 2.3e-03) | \|V + corte\| <= apoyos x 0.5e-4; V = Cs(G + fQ Q); F_i ~ W_i h_i | `python semana06/verificar_semana06.py` |
| Corte basal EY | **OK** | V = 10814.02 kN = 0.10 W; error 3.1e-04 kN (cota 2.3e-03) | \|V + corte\| <= apoyos x 0.5e-4; V = Cs(G + fQ Q); F_i ~ W_i h_i | `python semana06/verificar_semana06.py` |
| Superposicion | **OK** | 33/33 dentro de la cota; peor 1.000 de la cota | \|suma - explicita\| <= 0.5x10^-d (sum\|lambda\| + 1) + 4 eps sum\|lambda\| \|valor\| | `python comun/combinar.py conjunto` |
| M-phi | **OK** | Mn 1190.2 vs Whitney 1194.6 kN m (0.4 %); EI_cr 0.2 % | fibras vs a mano <= 2 %; 20 vs 40 fibras <= 0.5 % | `python comun/capacidad.py conjunto 200037 --sensibilidad` |
| P-M columna | **OK** | extremos exactos; flexion 0.4 %; u = 0.301 en 0.9G+1.4EX | traccion = -As fy; flexion vs Whitney <= 2 %; anexo = interaccion; u rehecha = anexo | `python semana03/verificar_rc.py conjunto 200037` |
| P-M muro | **PARCIAL** | 100537 u = 0.577 (0.589 fino); 200009 u = 0.662 (0.667 fino) | extremos exactos; plano por inercias; fibras = Whitney con las mismas hipotesis <= 2 % | `python semana03/verificar_rc.py conjunto 100537 (y 200009)` |
| IDs Unity | **OK** | 558 nodos y 937 elementos: mismo tag en modelo, visor, anexo y GameObject | contrato sano; 0 diferencias de tag, nodos, tipo, seccion y coordenadas | `python comun/test_contrato_unity.py conjunto` |
| AR | **OK** | app = OpenSees bit a bit; pose del marcador | verificar_ar.py sin FALLA; una captura del telefono en evidencia/iphone/ | `python semana06_lab/verificar_ar.py --sin-navegador` |

**Lo abierto** (lo que deja una fila en PARCIAL, medido por la misma prueba):

- P-M muro: 100537: el mallado de 20 fibras no alcanza en un muro de 16.85 m: a P = 0 sobreestima Mn en 4.3 % contra 40 (capacidad.py declara < 0.5 %)
- P-M muro: 100537: cerca de P = 0 la curva incluye el endurecimiento de Steel01 (+15.6 %): no es la capacidad nominal de ACI
- P-M muro: 200009: el mallado de 20 fibras no alcanza en un muro de 7.95 m: a P = 0 sobreestima Mn en 2.2 % contra 40 (capacidad.py declara < 0.5 %)
- P-M muro: 200009: cerca de P = 0 la curva incluye el endurecimiento de Steel01 (+11.6 %): no es la capacidad nominal de ACI
