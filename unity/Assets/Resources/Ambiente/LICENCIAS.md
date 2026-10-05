# Recursos de la vista realista

Todo lo de esta carpeta es **CC0** (dominio público: no exige
atribución, pero se nombra igual). Cada subcarpeta de `Texturas/` tiene
su `FUENTE.txt` con la página, el texto de la licencia y las URLs
exactas que se bajaron el 05-10-2026.

| Uso | Asset | Fuente | Autor |
|---|---|---|---|
| Columnas, vigas, muros | Concrete006 | ambientCG, https://ambientcg.com/view?id=Concrete006 | — |
| Losas, fondo de la excavación | Concrete024 | ambientCG, https://ambientcg.com/view?id=Concrete024 | — |
| Pasto | Grass005 | ambientCG, https://ambientcg.com/view?id=Grass005 | — |
| Tierra de los taludes | forest_ground_05 | Poly Haven, https://polyhaven.com/a/forest_ground_05 | Charlotte Baglioni |
| Perfiles de acero | Metal038 (galvanizado) | ambientCG, https://ambientcg.com/view?id=Metal038 | — |
| Cielo | kloofendal_48d_partly_cloudy_puresky (2K .hdr) | Poly Haven, https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky | Greg Zaal, Jarod Guest |

Se guardan solo los mapas que se usan (color y normal OpenGL, 1K, JPG
recomprimido a calidad 90) y el HDR tal cual. Los materiales
(`Mat_*.mat`), el cielo (`Cielo.mat`, girado con `Texturas/cielo/sol.json`)
y el post-proceso (`PerfilRealista.asset`) los arma
`unity/Assets/Editor/RecursosRealistas.cs`; los verifica
`python comun/recursos_realistas.py --verificar`.
