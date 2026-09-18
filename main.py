"""
Ponto de Entrada Principal (Entry Point) do Monitor SEI.
Carrega os módulos de monitoramento registrados, gera planilha modelo se necessário e inicia a interface gráfica.
"""

from pathlib import Path
import pandas as pd
from config.settings import UNIDADES_PADRAO, INPUTS_DIR
from monitors import MONITORES_DISPONIVEIS
from ui.app import AppMonitorSEI

def criar_planilha_modelo_se_necessario():
    """Gera uma planilha de exemplo em data/inputs/processos.xlsx caso não exista."""
    modelo_path = INPUTS_DIR / "processos.xlsx"
    if not modelo_path.exists():
        df_exemplo = pd.DataFrame({
            "processo": [
                "00000.000001/2026-01",
                "00000.000002/2026-02",
                "00000.000003/2026-03"
            ],
            "descricao_opcional": [
                "Processo Exemplo 1",
                "Processo Exemplo 2",
                "Processo Exemplo 3"
            ]
        })
        try:
            df_exemplo.to_excel(modelo_path, index=False)
        except Exception:
            pass

def main():
    # Cria template de processos caso a pasta data/inputs esteja vazia
    criar_planilha_modelo_se_necessario()

    # Inicializa a interface gráfica moderna (CustomTkinter)
    app = AppMonitorSEI(
        unidades=UNIDADES_PADRAO,
        monitores=MONITORES_DISPONIVEIS
    )
    app.mainloop()

if __name__ == "__main__":
    main()
