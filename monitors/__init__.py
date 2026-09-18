from .monitor_atas_feitas import MonitorAtasFeitas
from .monitor_andamentos import MonitorAndamentos
from .monitor_atas import MonitorAtas

# Lista de instâncias de monitores disponíveis para a interface gráfica
MONITORES_DISPONIVEIS = [
    MonitorAtasFeitas(),
    MonitorAndamentos(),
    MonitorAtas()
]

__all__ = ["MonitorAtasFeitas", "MonitorAndamentos", "MonitorAtas", "MONITORES_DISPONIVEIS"]
