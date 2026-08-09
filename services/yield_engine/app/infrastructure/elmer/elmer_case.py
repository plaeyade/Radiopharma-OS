"""
Generador de caso FEM para Elmer (ElmerFEM, CSC — software abierto GPL):
malla nativa + fichero SIF del problema térmico del blanco.

Elmer resuelve la ecuación del calor estacionaria 2D axisimétrica
(HeatSolver) sobre el dominio del blanco:

    −∇·(k∇T) = q'''(r)     en (r, z) ∈ [0, R] × [0, L]
    −k ∂T/∂n = h (T − T_ext)   en la cara refrigerada (z = L)
    ∂T/∂n = 0                  en el resto (condición natural)

La fuente volumétrica reproduce el haz gaussiano con la misma
normalización exacta del modelo reducido (∫ q''' dV = P):

    q'''(r) = q0 · exp(−r²/2σ²),   q0 = P · f_pico / (πR²L)

Elmer trabaja en SI (m, W, K): toda la conversión desde las unidades del
dominio (cm) se hace aquí, en un único lugar.

Formato de malla nativa de Elmer (directorio con 4 ficheros):
    mesh.header    n_nodos n_elementos n_frontera / n_tipos / código cuenta
    mesh.nodes     id  −1  x  y  z
    mesh.elements  id  cuerpo  tipo  n1..n4   (tipo 404 = cuadrilátero)
    mesh.boundary  id  bc  tipo  n1 n2        (tipo 202 = arista)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from app.domain.burnup_radial import gaussian_peak_factor
from app.domain.elmer_materials import MaterialProps

# Tipos de elemento del formato nativo Elmer
_EL_QUAD: int = 404
_EL_EDGE: int = 202
# BC id de la cara refrigerada (z = L)
BC_COOLED: int = 1


@dataclass(frozen=True)
class ElmerThermalCase:
    """Parámetros físicos del caso térmico FEM (unidades del dominio)."""
    beam_power_w: float
    spot_radius_cm: float
    target_thickness_cm: float
    conductivity_w_cm_k: float
    film_coeff_w_cm2_k: float
    coolant_temp_k: float
    beam_sigma_cm: float | None = None   # None → fuente uniforme


def write_mesh(case_dir: Path, case: ElmerThermalCase,
               n_r: int = 40, n_z: int = 20) -> Path:
    """Escribe la malla rectangular estructurada (cuadriláteros 404) en
    formato nativo Elmer. Devuelve el directorio de la malla."""
    if n_r < 2 or n_z < 2:
        raise ValueError("n_r y n_z deben ser >= 2")
    r_max = case.spot_radius_cm / 100.0       # m
    z_max = case.target_thickness_cm / 100.0  # m
    mesh_dir = case_dir / "mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    n_nodes = (n_r + 1) * (n_z + 1)
    n_elems = n_r * n_z
    n_bdry = n_r  # aristas de la cara superior (refrigerada)

    def node_id(i: int, j: int) -> int:
        return j * (n_r + 1) + i + 1

    with open(mesh_dir / "mesh.header", "w", encoding="utf-8") as fh:
        fh.write(f"{n_nodes} {n_elems} {n_bdry}\n2\n"
                 f"{_EL_QUAD} {n_elems}\n{_EL_EDGE} {n_bdry}\n")

    with open(mesh_dir / "mesh.nodes", "w", encoding="utf-8") as fh:
        for j in range(n_z + 1):
            z = z_max * j / n_z
            for i in range(n_r + 1):
                r = r_max * i / n_r
                fh.write(f"{node_id(i, j)} -1 {r:.10e} {z:.10e} 0.0\n")

    with open(mesh_dir / "mesh.elements", "w", encoding="utf-8") as fh:
        eid = 0
        for j in range(n_z):
            for i in range(n_r):
                eid += 1
                fh.write(f"{eid} 1 {_EL_QUAD} "
                         f"{node_id(i, j)} {node_id(i + 1, j)} "
                         f"{node_id(i + 1, j + 1)} {node_id(i, j + 1)}\n")

    with open(mesh_dir / "mesh.boundary", "w", encoding="utf-8") as fh:
        for i in range(n_r):
            # formato nativo: id  bc  padre  0  tipo  n1  n2
            padre = (n_z - 1) * n_r + i + 1   # cuadrilátero adyacente
            fh.write(f"{i + 1} {BC_COOLED} {padre} 0 {_EL_EDGE} "
                     f"{node_id(i, n_z)} {node_id(i + 1, n_z)}\n")

    return mesh_dir


def _heat_source_block(case: ElmerThermalCase, r_max: float,
                       z_max: float) -> str:
    """Bloque SIF de la fuente volumétrica (W/m³), gaussiana MATC o
    uniforme, con normalización exacta ∫ q''' dV = P."""
    volume = math.pi * r_max * r_max * z_max       # m³
    if case.beam_sigma_cm is not None:
        sigma = case.beam_sigma_cm / 100.0
        factor = gaussian_peak_factor(case.spot_radius_cm, case.beam_sigma_cm)
        q0 = case.beam_power_w * factor / volume
        return (
            "  Volumetric Heat Source = Variable Coordinate 1\n"
            f'    Real MATC "{q0:.10e}*exp(-(tx(0))^2/(2*{sigma:.10e}^2))"\n')
    q0 = case.beam_power_w / volume
    return f"  Volumetric Heat Source = Real {q0:.10e}\n"


def write_sif(case_dir: Path, case: ElmerThermalCase,
              density_kg_m3: float = 1000.0,
              heat_capacity_j_kg_k: float = 4180.0) -> Path:
    """Escribe case.sif (Heat Equation estacionaria, axisimétrica) y
    devuelve su ruta. La fuente gaussiana se expresa en MATC."""
    r_max = case.spot_radius_cm / 100.0
    k_si = case.conductivity_w_cm_k * 100.0        # W/(cm·K) → W/(m·K)
    h_si = case.film_coeff_w_cm2_k * 1.0e4         # W/(cm²·K) → W/(m²·K)
    heat_source = _heat_source_block(case, r_max,
                                     case.target_thickness_cm / 100.0)

    sif = f"""Header
  CHECK KEYWORDS Warn
  Mesh DB "." "mesh"
  Include Path ""
  Results Directory ""
End

Simulation
  Max Output Level = 5
  Coordinate System = "Axi Symmetric"
  Simulation Type = "Steady state"
  Steady State Max Iterations = 1
  Output Intervals(1) = 1
  Post File = "case.vtu"
End

Body 1
  Target Bodies(1) = 1
  Name = "Target"
  Equation = 1
  Material = 1
  Body Force = 1
End

Solver 1
  Equation = "Heat Equation"
  Variable = "Temperature"
  Procedure = "HeatSolve" "HeatSolver"
  Exec Solver = "Always"
  Stabilize = True
  Optimize Bandwidth = True
  Linear System Solver = "Iterative"
  Linear System Iterative Method = "BiCGStab"
  Linear System Max Iterations = 500
  Linear System Convergence Tolerance = 1.0e-10
  Linear System Preconditioning = "ILU0"
  Nonlinear System Max Iterations = 1
  Nonlinear System Convergence Tolerance = 1.0e-07
  Steady State Convergence Tolerance = 1.0e-06
End

Solver 2
  Equation = "SaveScalars"
  Procedure = "SaveData" "SaveScalars"
  Filename = "scalars.dat"
  Variable 1 = "Temperature"
  Operator 1 = "max"
  Variable 2 = "Temperature"
  Operator 2 = "mean"
End

Equation 1
  Active Solvers(2) = 1 2
End

Material 1
  Name = "TargetMaterial"
  Density = Real {density_kg_m3:.6e}
  Heat Capacity = Real {heat_capacity_j_kg_k:.6e}
  Heat Conductivity = Real {k_si:.10e}
End

Body Force 1
{heat_source}End

Boundary Condition 1
  Target Boundaries(1) = {BC_COOLED}
  Name = "CooledFace"
  Heat Transfer Coefficient = Real {h_si:.10e}
  External Temperature = Real {case.coolant_temp_k:.6e}
End
"""
    sif_path = case_dir / "case.sif"
    sif_path.write_text(sif, encoding="utf-8")
    return sif_path


def build_case(case_dir: Path, case: ElmerThermalCase,
               n_r: int = 40, n_z: int = 20) -> Path:
    """Genera malla + SIF en case_dir y devuelve la ruta del SIF."""
    case_dir.mkdir(parents=True, exist_ok=True)
    write_mesh(case_dir, case, n_r=n_r, n_z=n_z)
    return write_sif(case_dir, case)


def write_sif_thermomechanical(case_dir: Path, case: ElmerThermalCase,
                               material: MaterialProps) -> Path:
    """SIF termo-mecánico acoplado (EDS 18.13): Heat Equation → Stress
    Analysis secuencial sobre la misma malla; SaveScalars extrae las
    cuatro magnitudes canónicas (18.2/18.12): temperatura máxima/media,
    tensión equivalente de von Mises máxima y desplazamiento máximo.

    Simplificación mecánica documentada: la cara refrigerada se modela
    empotrada (desplazamiento nulo), lo que representa el borde sujeto
    del blanco/ventana; el resto de contornos quedan libres."""
    r_max = case.spot_radius_cm / 100.0
    k_si = case.conductivity_w_cm_k * 100.0
    h_si = case.film_coeff_w_cm2_k * 1.0e4
    heat_source = _heat_source_block(case, r_max,
                                     case.target_thickness_cm / 100.0)

    sif = f"""Header
  CHECK KEYWORDS Warn
  Mesh DB "." "mesh"
  Include Path ""
  Results Directory ""
End

Simulation
  Max Output Level = 5
  Coordinate System = "Axi Symmetric"
  Simulation Type = "Steady state"
  Steady State Max Iterations = 1
  Output Intervals(1) = 1
  Post File = "case.vtu"
End

Body 1
  Target Bodies(1) = 1
  Name = "Target"
  Equation = 1
  Material = 1
  Body Force = 1
End

Solver 1
  Equation = "Heat Equation"
  Variable = "Temperature"
  Procedure = "HeatSolve" "HeatSolver"
  Exec Solver = "Always"
  Stabilize = True
  Optimize Bandwidth = True
  Linear System Solver = "Iterative"
  Linear System Iterative Method = "BiCGStab"
  Linear System Max Iterations = 500
  Linear System Convergence Tolerance = 1.0e-10
  Linear System Preconditioning = "ILU0"
  Nonlinear System Max Iterations = 1
  Nonlinear System Convergence Tolerance = 1.0e-07
  Steady State Convergence Tolerance = 1.0e-06
End

Solver 2
  Equation = "Stress Analysis"
  Variable = -dofs 2 "Displacement"
  Procedure = "StressSolve" "StressSolver"
  Exec Solver = "Always"
  Calculate Stresses = True
  Linear System Solver = "Iterative"
  Linear System Iterative Method = "BiCGStab"
  Linear System Max Iterations = 500
  Linear System Convergence Tolerance = 1.0e-10
  Linear System Preconditioning = "ILU0"
  Nonlinear System Max Iterations = 1
  Nonlinear System Convergence Tolerance = 1.0e-07
  Steady State Convergence Tolerance = 1.0e-06
End

Solver 3
  Equation = "SaveScalars"
  Procedure = "SaveData" "SaveScalars"
  Filename = "scalars.dat"
  Variable 1 = "Temperature"
  Operator 1 = "max"
  Variable 2 = "Temperature"
  Operator 2 = "mean"
  Variable 3 = "vonMises"
  Operator 3 = "max"
  Variable 4 = "Displacement"
  Operator 4 = "max"
End

Equation 1
  Active Solvers(3) = 1 2 3
End

Material 1
  Name = "{material.material_id} v{material.version}"
  Density = Real {material.densidad_kg_m3:.6e}
  Heat Capacity = Real {material.calor_especifico_j_kg_k:.6e}
  Heat Conductivity = Real {k_si:.10e}
  Youngs Modulus = Real {material.young_pa:.10e}
  Poisson Ratio = Real {material.poisson:.6f}
  Heat Expansion Coefficient = Real {material.expansion_termica_1_k:.10e}
  Reference Temperature = Real {case.coolant_temp_k:.6e}
End

Body Force 1
{heat_source}End

Boundary Condition 1
  Target Boundaries(1) = {BC_COOLED}
  Name = "CooledFace"
  Heat Transfer Coefficient = Real {h_si:.10e}
  External Temperature = Real {case.coolant_temp_k:.6e}
  Displacement 1 = Real 0.0
  Displacement 2 = Real 0.0
End
"""
    sif_path = case_dir / "case.sif"
    sif_path.write_text(sif, encoding="utf-8")
    return sif_path


def build_case_thermomechanical(case_dir: Path, case: ElmerThermalCase,
                                material: MaterialProps,
                                n_r: int = 40, n_z: int = 20) -> Path:
    """Malla + SIF termo-mecánico (18.13)."""
    case_dir.mkdir(parents=True, exist_ok=True)
    write_mesh(case_dir, case, n_r=n_r, n_z=n_z)
    return write_sif_thermomechanical(case_dir, case, material)
