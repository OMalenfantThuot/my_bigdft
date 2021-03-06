r"""
The :class:`Logfile` class is the base class you want to be
using all the time. It is mainly meant to manipulate the output of a BigDFT
calculation (written using the YAML format).

However, it might happen that the output actually contains many documents (for
instance, one document per geometry optimization procedure). In such cases,
the initialization of a ``Logfile`` actually gives another type of object,
deriving from the :class:`MultipleLogfile` class. Be careful:
these objects behave as a list of ``Logfile`` instances, not as a ``Logfile``
instance (even though they are initialized *via* the ``Logfile`` class).
To keep the same example as above, the output file of a geometry optimization
calculation can be read via the :meth:`Logfile.from_file`
method of the ``Logfile`` class, returning a
:class:`GeoptLogfile` instance.
"""

from __future__ import print_function
import warnings
from collections import Sequence, Mapping
from copy import deepcopy
import yaml

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:  # pragma: no cover
    from yaml import Loader, Dumper
import numpy as np
from mybigdft.globals import INPUT_PARAMETERS_DEFINITIONS
from .inputparams import InputParams, clean
from .posinp import Posinp


__all__ = ["Logfile", "MultipleLogfile", "GeoptLogfile"]


PATHS = "paths"
DOC = "doc"
LAST_GROUND_STATE_OPTIMIZATION = ["Ground State Optimization", -1]
LAST_SUBSPACE_OPTIMIZATION = LAST_GROUND_STATE_OPTIMIZATION + [
    "Hamiltonian Optimization",
    -1,
    "Subspace Optimization",
]


def _get_value_from_last_optimization(key):
    r"""
    """
    l_1 = deepcopy(LAST_GROUND_STATE_OPTIMIZATION)
    l_1.append(key)
    l_2 = deepcopy(LAST_SUBSPACE_OPTIMIZATION)
    l_2.append(key)
    return [l_1, l_2]


ATTRIBUTES = {
    "n_at": {
        PATHS: [["Atomic System Properties", "Number of atoms"]],
        DOC: "Number of Atoms",
    },
    "boundary_conditions": {
        PATHS: [["Atomic System Properties", "Boundary Conditions"]],
        DOC: "Boundary Conditions",
    },
    "cell": {PATHS: [["Atomic System Properties", "Box Sizes (AU)"]], DOC: "Cell size"},
    "symmetry": {
        PATHS: [["Atomic System Properties", "Space group"]],
        DOC: "Symmetry group",
    },
    "atom_types": {
        PATHS: [["Atomic System Properties", "Types of atoms"]],
        DOC: "List of the atomic types present in the posinp",
    },
    "energy": {
        PATHS: [
            ["Last Iteration", "FKS"],
            ["Last Iteration", "EKS"],
            ["Energy (Hartree)"],
        ],
        DOC: "Energy (Hartree)",
    },
    "astruct": {PATHS: [["Atomic structure"]], DOC: "Atomic structure"},
    "evals": {
        PATHS: [["Complete list of energy eigenvalues"]]
        + _get_value_from_last_optimization("Orbitals"),
        DOC: "Orbital energies and occupations",
    },
    "fermi_level": {
        PATHS: _get_value_from_last_optimization("Fermi Energy"),
        DOC: "Fermi level",
    },
    "magnetization": {
        PATHS: _get_value_from_last_optimization("Total magnetization"),
        DOC: "Total magnetization of the system",
    },
    "kpt_mesh": {PATHS: [["kpt", "ngkpt"]], DOC: "No. of Monkhorst-Pack grid points"},
    "kpts": {PATHS: [["K points"]], DOC: "Grid of k-points"},
    "gnrm_cv": {
        PATHS: [["dft", "gnrm_cv"]],
        DOC: "Convergence criterion on wavefunction residue",
    },
    "forcemax_cv": {
        PATHS: [["geopt", "forcemax"]],
        DOC: "Convergence criterion on forces",
    },
    "forcemax": {
        PATHS: [
            ["Geometry", "FORCES norm(Ha/Bohr)", "maxval"],
            ["Clean forces norm (Ha/Bohr)", "maxval"],
        ],
        DOC: "Maximum value of forces",
    },
    "pressure": {PATHS: [["Pressure", "GPa"]], DOC: "Pressure (GPa)"},
    "dipole": {
        PATHS: [["Electric Dipole Moment (AU)", "P vector"]],
        DOC: "Electric Dipole Moment (AU)",
    },
    "forces": {PATHS: [["Atomic Forces (Ha/Bohr)"]], DOC: "Atomic Forces (Ha/Bohr)"},
    "force_fluct": {
        PATHS: [["Geometry", "FORCES norm(Ha/Bohr)", "fluct"]],
        DOC: "Threshold fluctuation of Forces",
    },
    "support_functions": {
        PATHS: [
            ["Gross support functions moments", "Multipole coefficients", "values"]
        ],
        DOC: "Support functions",
    },
    "electrostatic_multipoles": {
        PATHS: [["Multipole coefficients", "values"]],
        DOC: "Electrostatic multipoles",
    },
    "sdos": {PATHS: [["SDos files"]], DOC: "SDos files"},
    "walltime": {
        PATHS: [["Walltime since initialization"]],
        DOC: "Walltime since initialization",
    },
    "WARNINGS": {PATHS: [["WARNINGS"]], DOC: "Warnings raised during the BigDFT run"},
}


class Logfile(Mapping):
    r"""
    Class allowing to initialize, read, write and interact with an
    output file of a BigDFT calculation.
    """

    def __init__(self, log=None):
        r"""
        Parameters
        ----------
        log : dict
            Output of the BigDFT code as a yaml dictionary.
        """
        if log is None:
            log = {}
        self._log = log
        self._set_builtin_attributes()
        self._clean_attributes()
        # It might happen that a geopt calculation has a step whose log
        # looks like it is incomplete, but they are actually acceptable.
        # To that end, we look for a specific warning message in one of
        # the logs (except the initial one). To make sure the current
        # log is not the initial one, we look for the "geopt" key, which
        # is not repreated in the subsequent logs. It's a workaround
        # which might prove edgy in the future.
        if "geopt" not in self.log:
            avoidable_warning = (
                "The norm of the residue is too large, need "
                "to recalculate input wavefunctions"
            )
            warnings = log.get("WARNINGS")
            acceptable_though_incomplete = (
                warnings is not None and avoidable_warning in warnings
            )
        else:
            acceptable_though_incomplete = False
        # Check if the logfile is incomplete
        if (
            self.log != {}
            and not acceptable_though_incomplete
            and (self.energy is None and self.forces is None and self.walltime is None)
        ):
            raise ValueError("The logfile is incomplete!")
        params = {key: log.get(key) for key in INPUT_PARAMETERS_DEFINITIONS}
        params = clean(params)
        self._inputparams = InputParams(params=params)
        self._posinp = self.inputparams.posinp
        self._check_warnings()

    def _set_builtin_attributes(self):
        r"""
        Set all the base attributes of a BigDFT Logfile.

        They are defined by the ATTRIBUTES dictionary, whose keys are
        the base name of each attribute, the values being the
        description of the attribute as another dictionary.

        Once retrieved from the logfile, the attributes are set under
        their base name preceded by an underscore (e.g., the number of
        atoms read thanks to the `n_at` key of ATTRIBUTES is finally
        stored as the attribute `_n_at` of the Logfile instance).
        This extra underscore is meant to prevent the user from updating
        the value of the attribute.
        """
        for name, description in ATTRIBUTES.items():
            # Loop over the various paths (or logfile levels) where the
            # value might be stored.
            for path in description[PATHS]:
                # Loop over the different levels of the logfile to
                # retrieve the value
                value = self  # Always start from the bare logfile
                for key in path:
                    try:
                        value = value.get(key)  # value can be a dict
                    except AttributeError:
                        try:
                            value = value[key]  # value can be a list
                        except TypeError:
                            # This path leads to a dead-end: set a
                            # default value before moving to the next
                            # possible path.
                            value = None
                            continue
                if value is not None:
                    # A value was found: no need to look for other paths
                    break
            # Set the value to the underscored attribute
            setattr(self, "_" + name, value)
            # Set the attribute as a property
            setattr(
                self.__class__,
                name,
                property(self._init_getter(name), doc=description.get(DOC, "")),
            )

    def _init_getter(self, name):
        def getter(self):
            return getattr(self, "_" + name)

        return getter

    def _clean_attributes(self):
        r"""
        Clean the value of the built-in attributes.
        """
        if self.boundary_conditions is not None:
            self._boundary_conditions = self._boundary_conditions.lower()
        # Make the forces as a numpy array of shape (n_at, 3)
        if self.forces is not None:
            new_forces = np.array([])
            for force in self.forces:
                new_forces = np.append(new_forces, list(force.values())[0])
            n_at = len(self.forces)
            new_forces = new_forces.reshape((n_at, 3))
            self._forces = new_forces

    def _check_warnings(self):
        r"""
        Warns
        -----
        UserWarning
            If there are some warnings in the Logfile or if the XC of
            the pseudo-potentials do not match those of the input
            parameters.
        """
        if self.WARNINGS is not None:
            for message in self.WARNINGS:
                if isinstance(message, dict):
                    # It might happen that a ":" symbol is in the
                    # description of a warning, hence it is decoded as a
                    # dictionary; make sure to treat it as a string
                    # instead
                    key, value = list(message.items())[0]
                    message = "{}: {}".format(key, value)
                elif not isinstance(message, str):  # pragma: no cover
                    print("MyBigDFT: weird error message found")
                    message = str(message)
                warnings.warn(message, UserWarning)
        self._check_psppar()

    def _check_psppar(self):
        r"""
        Warns
        -----
        UserWarning
            If the XC of the potential is different from the XC of the
            input parameters.
        """
        if self.atom_types is not None:
            for atom_type in self.atom_types:
                psp = "psppar.{}".format(atom_type)
                psp_ixc = self[psp]["Pseudopotential XC"]
                inp_ixc = self["dft"]["ixc"]
                if psp_ixc != inp_ixc:
                    warnings.warn(
                        "The XC of pseudo potentials ({}) is different from "
                        "the input XC ({}) for the '{}' atoms".format(
                            psp_ixc, inp_ixc, atom_type
                        ),
                        UserWarning,
                    )

    @classmethod
    def from_file(cls, filename):
        r"""
        Initialize the Logfile from a file on disk.

        Parameters
        ----------
        filename : str
            Name of the logfile.

        Returns
        -------
        Logfile or GeoptLogfile or MultipleLogfile
            Logfile initialized from a file on disk.


        >>> log = Logfile.from_file("tests/log.yaml")
        >>> print(log.posinp)
        2   angstroem
        free
        N   2.97630782434901e-23   6.87220595204354e-23   0.0107161998748779
        N  -1.10434491945017e-23  -4.87342174483075e-23   1.10427379608154
        <BLANKLINE>
        >>> log.energy
        -19.884659235401838
        """
        with open(filename, "r") as stream:
            return cls.from_stream(stream)

    @classmethod
    def from_stream(cls, stream):
        r"""
        Initialize the Logfile from a stream.

        Parameters
        ----------
        stream
            Logfile as a stream.

        Returns
        -------
        Logfile or GeoptLogfile or MultipleLogfile
            Logfile initialized from a stream.
        """
        # The logfile might contain multiple documents
        docs = yaml.load_all(stream, Loader=Loader)
        logs = [cls(doc) for doc in docs]
        if len(logs) == 1:
            # If only one document, return a Logfile instance
            return logs[0]
        else:
            if logs[0].inputparams["geopt"] is not None:
                # If the logfile corresponds to a geopt calculation,
                # return a GeoptLogfile instance
                return GeoptLogfile(logs)
            else:
                warnings.warn(
                    "More than one document found in the logfile!", UserWarning
                )
                # In other cases, just return a MultipleLogfile instance
                return MultipleLogfile(logs)

    @property
    def log(self):
        r"""
        Returns
        -------
        Logfile
            Yaml dictionary of the output of the BigDFT code.
        """
        return self._log

    def __dir__(self):
        r"""
        The base attributes are not found when doing `dir()` on a
        `Logfile` instance, but their counterpart with a preceding
        underscore is. What is done here is a removal of the underscored
        names, replaced by the bare names (in order to avoid name
        repetition).

        The bare attributes still behave as properties, while their
        value might be updated via the underscored attribute.
        """
        hidden_attributes = list(ATTRIBUTES.keys())
        try:  # pragma: no cover
            base_dir = super(Logfile, self).__dir__()  # Python3
        except AttributeError:  # pragma: no cover
            base_dir = dir(super(Logfile, self))  # Python2
            # Add the missing stuff
            base_dir += [
                "write",
                "log",
                "from_file",
                "from_stream",
                "posinp",
                "values",
                "keys",
                "get",
                "items",
                "inputparams",
                "_check_psppar",
                "_check_warnings",
                "_clean_attributes",
                "_set_builtin_attributes",
                "_init_getter",
            ]
            base_dir += hidden_attributes
        # Always remove the underscored attributes (so that there are less
        # elements in the returned list)
        for name in hidden_attributes:
            base_dir.remove("_" + name)
        return base_dir

    def __getitem__(self, key):
        return self.log[key]

    def __iter__(self):
        return iter(self.log)

    def __len__(self):
        return len(self.log)

    def __repr__(self):  # pragma: no cover
        return repr(self.log)

    def write(self, filename):
        r"""
        Write the logfile on disk.

        Parameters
        ----------
        filename : str
            Name of the logfile.
        """
        with open(filename, "w") as stream:
            yaml.dump(self.log, stream=stream, Dumper=Dumper)

    @property
    def posinp(self):
        r"""
        Returns
        -------
        Posinp
            Posinp used during the calculation.
        """
        return self._posinp

    @property
    def inputparams(self):
        r"""
        Returns
        -------
        InputParams
            Input parameters used during the calculation.
        """
        return self._inputparams


class MultipleLogfile(Sequence):
    r"""
    Class allowing to initialize, read, write and interact with an
    output file of a BigDFT calculation containing multiple documents.
    """

    def __init__(self, logs):
        r"""
        Parameters
        ----------
        logs : list
            List of the various documents contained in the logfile of a
            BigDFT calculation.
        """
        self._logs = logs

    @property
    def logs(self):
        r"""
        Returns
        -------
        list
            List of the documents read from a single output of a BigDFT
            calculation.
        """
        return self._logs

    def __getitem__(self, index):
        return self.logs[index]

    def __len__(self):
        return len(self.logs)

    def write(self, filename):
        r"""
        Write the logfile on disk.

        Parameters
        ----------
        filename : str
            Name of the logfile.
        """
        logs = [log.log for log in self.logs]
        with open(filename, "w") as stream:
            yaml.dump_all(logs, stream=stream, Dumper=Dumper, explicit_start=True)


class GeoptLogfile(MultipleLogfile):
    r"""
    Class allowing to initialize, read, write and interact with an
    output file of a geometry optimization calculation.
    """

    def __init__(self, logs):
        r"""
        Parameters
        ----------
        logs : list
            List of the various documents contained in the logfile of a
            geometry optimization calculation.
        """
        super(GeoptLogfile, self).__init__(logs)
        # Update the input parameters and positions of the documents
        for log in self.logs[1:]:
            log._inputparams = self.inputparams
            log._posinp = Posinp.from_dict(log["Atomic structure"])
        self._posinps = [log.posinp for log in self.logs]

    @property
    def inputparams(self):
        r"""
        Returns
        -------
        InputParams
            Input parameters used for each step of the geometry
            optimization procedure.
        """
        return self.logs[0].inputparams

    @property
    def posinps(self):
        r"""
        Returns
        -------
        list
            List of the input positions for each step of the geometry
            optimization procedure.
        """
        return self._posinps
