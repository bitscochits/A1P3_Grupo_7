/*
================================================================
  VisorQA.Entorno.cs
================================================================
  Las casillas "Ventanas" y "Autos y arboles" de Capas > Vista, debajo
  de la del relieve. Van en su propio archivo (VisorQA es partial) para
  no correr las lineas de VisorQA.cs que citan los informes: las llama
  VisorQA.Relieve.cs al final de su casilla.

  Siempre dibuja los mismos tres controles (dos casillas y la nota),
  haya o no entorno: cambiar la cantidad de controles a mitad de un
  evento de IMGUI hace saltar "Getting control N's position". El cambio
  se difiere a Update, como el resto del panel.
================================================================
*/

using UnityEngine;

public partial class VisorQA
{
    void CasillasEntorno()
    {
        GUILayout.BeginHorizontal();
        bool ventanas = GUILayout.Toggle(AjustesVista.ventanas, "Ventanas", estToggle, GUILayout.ExpandWidth(false));
        bool entorno = GUILayout.Toggle(AjustesVista.entorno, "Autos y arboles", estToggle, GUILayout.ExpandWidth(false));
        GUILayout.EndHorizontal();
        if (ventanas != AjustesVista.ventanas)
            Diferir(() => { AjustesVista.ventanas = ventanas; EventosVisor.AvisarVistaCambio(); });
        if (entorno != AjustesVista.entorno)
            Diferir(() => { AjustesVista.entorno = entorno; EventosVisor.AvisarVistaCambio(); });
        GUILayout.Label(string.IsNullOrEmpty(AjustesVista.entornoEstado)
            ? "Ventanas, autos y arboles: todavia no se carga el modelo."
            : AjustesVista.entornoEstado, PanelUI.Tenue);
    }
}
