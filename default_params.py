import numpy as np
device_rank = 0
complex_dtype = "complex"
real_dtype = "float64"
BOX_SIZE_DEFAULT = True

L  =  [10, 10, 10]

if BOX_SIZE_DEFAULT:
    L = [2*np.pi, 2*np.pi, 2*np.pi]

Rac = 27*np.pi**4/4
Ra = 5e5*Rac
Pr = 6.8

kappa = 1/np.sqrt(Ra*Pr)
maintain_mux = 1
injections = [0,0,0]
gpu_direct_storage = False
Omega = [0,0,0]
Nb = 0
HYPO_DISSIPATION = False
HYPER_DISSIPATION = False

nu_hypo_cutoff = -1
eta_hypo_cutoff = -1

kappa_hypo_cutoff = -1

kappa_hypo = 1
kappa_hypo_power = -2
kappa_hyper = 1E-4
kappa_hyper_power = 2
ROTATION_ENABLED = False
MAINTAIN_FIELD = False
PRINT_PARAMETERS = True
USE_BINDING = True
PLANAR_SPECTRA = False
SAVE_VORTICITY = False
SAVE_VECPOT = False
VALIDATE_SOLVER = False
t_eps = 1e-8
#FORCING_ENABLED = False
RUNTIME_SAVE = True
INPUT_SET_CASE = True
input_case = 'custom'

INPUT_FROM_FILE = False
INPUT_REAL_FIELD = False
INPUT_ELSASSER = False
OUTPUT_REAL_FIELD = False
FORCING_SCHEME = 'random'
RANDOM_FORCING_TYPE = 'u'
BUOYANCY_ENABLED = False
LIVE_PLOT = False