from __future__ import absolute_import
import os
import pytest
import numpy as np
from mybigdft import Atom, Posinp, Job, InputParams
from mybigdft.workflows import (
    PolTensor, Phonons, RamanSpectrum, Geopt, Dissociation, InfraredSpectrum,
    VibPolTensor,
)
from mybigdft.workflows.workflow import Workflow

pos = Posinp(
    [Atom('N', [0, 0, 0]), Atom('N', [0, 0, 1.095])], 'angstroem', 'free')


class TestWorkflow:

    def test_init(self):
        wf = Workflow()
        assert wf.queue == []

    def test_run(self):
        wf = Workflow()
        wf.run()
        assert wf.completed
        assert wf.is_completed


class TestPolTensor:

    # Polarizibility tensor workflow which is not run
    inp = InputParams({'dft': {'hgrids': [0.55]*3}})
    gs = Job(inputparams=inp, posinp=pos, name='N2', run_dir='pol_tensor_N2')
    pt = PolTensor(gs)

    @pytest.mark.parametrize("value, expected", [
        (pt.ground_state, gs),
        (pt.is_completed, False),
        (pt.ef_amplitudes, [1.e-4]*3),
        (os.path.basename(pt.ground_state.run_dir), "pol_tensor_N2"),
    ])
    def test_init(self, value, expected):
        assert value == expected

    def test_init_warns_UserWarning(self):
        test_inp = InputParams({'dft': {'elecfield': [0.1]*3}})
        job = Job(inputparams=test_inp, posinp=pos)
        with pytest.warns(UserWarning):
            PolTensor(job)

    @pytest.mark.parametrize("to_evaluate", [
        'PolTensor(self.gs, ef_amplitudes=0.0)',
        'PolTensor(self.gs, ef_amplitudes=[0.0])',
        'PolTensor(self.gs, ef_amplitudes=[0.1]*4)',
    ])
    def test_init_ef_amplitudes_raises_ValueError(self, to_evaluate):
        with pytest.raises(ValueError):
            eval(to_evaluate)

    def test_init_raises_NotImplementedError(self):
        with pytest.raises(NotImplementedError):
            PolTensor(self.gs, order=-1)

    def test_run_first_order(self):
        # Run a pol. tensor calculation
        gs2 = Job(posinp=pos, name='N2', run_dir='tests/pol_tensor_N2')
        pt2 = PolTensor(gs2, order=1)
        assert not pt2.is_completed
        pt2.run()
        assert pt2.is_completed
        # Test the computed polarizability tensor
        expected = [
            [1.05558000e+01, -2.00000000e-04, 0.00000000e+00],
            [-2.00000000e-04, 1.05558000e+01, 0.00000000e+00],
            [-2.00000000e-04, -2.00000000e-04, 1.50535000e+01]
        ]
        np.testing.assert_almost_equal(pt2.pol_tensor, expected)
        np.testing.assert_almost_equal(pt2.mean_polarizability, 12.05503333333)
        # Test that running the workflow again warns a UserWarning
        with pytest.warns(UserWarning):
            pt2.run()

    def test_run_second_order(self):
        # Run a pol. tensor calculation
        gs2 = Job(posinp=pos, name='N2', run_dir='tests/pol_tensor_N2')
        pt2 = PolTensor(gs2, order=2)
        assert not pt2.is_completed
        pt2.run()
        assert pt2.is_completed
        # Test the computed polarizability tensor
        expected = [
            [1.055590e+01, -3.000000e-04, 0.000000e+00],
            [-3.000000e-04, 1.055590e+01, 0.000000e+00],
            [-3.500000e-04, -3.500000e-04, 1.505375e+01]
        ]
        np.testing.assert_almost_equal(pt2.pol_tensor, expected)
        np.testing.assert_almost_equal(pt2.mean_polarizability, 12.05518333333)
        # Test that running the workflow again warns a UserWarning
        with pytest.warns(UserWarning):
            pt2.run()


class TestPhonons:

    gs = Job(posinp=pos, name='N2', run_dir='tests/phonons_N2')

    @pytest.mark.parametrize("to_evaluate", [
        "Phonons(self.gs, translation_amplitudes=1)",
        "Phonons(self.gs, translation_amplitudes=[3]*2)",
        "Phonons(self.gs, translation_amplitudes=[3]*4)",
    ])
    def test_init_raises_ValueError(self, to_evaluate):
        with pytest.raises(ValueError):
            eval(to_evaluate)

    def test_init_raises_NotImplementedError(self):
        with pytest.raises(NotImplementedError):
            Phonons(self.gs, order=-1)

    def test_run_first_order(self):
        N2_ref = """\
2   angstroem
free
N   3.571946174   3.571946174   3.620526682
N   3.571946174   3.571946174   4.71401439"""
        ref_pos = Posinp.from_string(N2_ref)
        gs = Job(posinp=ref_pos, name='N2', run_dir='tests/phonons_N2')
        ph = Phonons(gs, order=1)
        assert not ph.is_completed
        ph.run(nmpi=2, nomp=2)
        assert ph.is_completed
        # Test the only physically relevant phonon energy
        np.testing.assert_almost_equal(
            max(ph.energies), 2386.9850607523636, decimal=6)


class TestRamanSpectrum:

    gs = Job(posinp=pos, name='N2', run_dir='tests/phonons_N2')
    ph = Phonons(gs)

    def test_run_first_order_phonons(self):
        N2_ref = """\
2   angstroem
free
N   3.571946174   3.571946174   3.620526682
N   3.571946174   3.571946174   4.71401439"""
        ref_pos = Posinp.from_string(N2_ref)
        gs = Job(posinp=ref_pos, name='N2', run_dir='tests/phonons_N2')
        phonons = Phonons(gs, order=1)
        raman = RamanSpectrum(phonons)
        assert not phonons.is_completed
        assert not raman.is_completed
        raman.run(nmpi=2, nomp=2)
        assert phonons.is_completed
        assert raman.is_completed
        # Test the only physically relevant phonon energy
        np.testing.assert_almost_equal(
            max(raman.energies), 2386.9850607466974, decimal=6)
        # Test the only physically relevant intensity
        np.testing.assert_almost_equal(
            max(raman.intensities), 22.561427637014187)
        # Test the only physically relevant depolarization ratio
        i = np.argmax(raman.energies)
        np.testing.assert_almost_equal(
            raman.depolarization_ratios[i], 0.09412532271275614)
        # Test that running the workflow again warns a UserWarning
        with pytest.warns(UserWarning):
            phonons.run()
        with pytest.warns(UserWarning):
            raman.run()

    def test_run_second_order_phonons(self):
        N2_ref = """\
2   angstroem
free
N   3.571946174   3.571946174   3.620526682
N   3.571946174   3.571946174   4.71401439"""
        ref_pos = Posinp.from_string(N2_ref)
        gs = Job(posinp=ref_pos, name='N2', run_dir='tests/phonons_N2')
        phonons = Phonons(gs, order=2)
        raman = RamanSpectrum(phonons)
        assert not phonons.is_completed
        assert not raman.is_completed
        raman.run(nmpi=2, nomp=2)
        assert phonons.is_completed
        assert raman.is_completed
        # Test the only physically relevant phonon energy
        np.testing.assert_almost_equal(
            max(raman.energies), 2386.9463343478246, decimal=6)
        # Test the only physically relevant intensity
        np.testing.assert_almost_equal(
            max(raman.intensities), 22.564457304830206)
        # Test the only physically relevant depolarization ratio
        i = np.argmax(raman.energies)
        np.testing.assert_almost_equal(
            raman.depolarization_ratios[i], 0.09412173797731693)
        # Test that running the workflow again warns a UserWarning
        with pytest.warns(UserWarning):
            phonons.run()
        with pytest.warns(UserWarning):
            raman.run()

    @pytest.mark.parametrize("to_evaluate", [
        "RamanSpectrum(self.ph, ef_amplitudes=1)",
        "RamanSpectrum(self.ph, ef_amplitudes=[3]*2)",
        "RamanSpectrum(self.ph, ef_amplitudes=[3]*4)",
    ])
    def test_init_raises_ValueError(self, to_evaluate):
        with pytest.raises(ValueError):
            eval(to_evaluate)


class TestInfraredSpectrum:

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_run(self):
        atoms = [Atom('N', [3.571946174, 3.571946174, 3.620526682]),
                 Atom('N', [3.571946174, 3.571946174, 4.71401439])]
        pos = Posinp(atoms, units="angstroem", boundary_conditions="free")
        gs = Job(posinp=pos, name='N2', run_dir='tests/phonons_N2')
        ph = Phonons(gs)
        ir = InfraredSpectrum(ph)
        assert not ir.is_completed
        ir.run()
        assert ir.is_completed
        # Test the only physically relevant infrared intensity
        i = np.argmax(ir.energies)
        np.testing.assert_almost_equal(ir.intensities[i], 1.100446469749e-06)
        # Test that running the workflow again warns a UserWarning
        with pytest.warns(UserWarning):
            ir.run()


class TestVibPolTensor:

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_run(self):
        atoms = [Atom('N', [3.571946174, 3.571946174, 3.620526682]),
                 Atom('N', [3.571946174, 3.571946174, 4.71401439])]
        pos = Posinp(atoms, units="angstroem", boundary_conditions="free")
        gs = Job(posinp=pos, name='N2', run_dir='tests/phonons_N2')
        ph = Phonons(gs)
        ir = InfraredSpectrum(ph)
        vpt = VibPolTensor(ir)
        assert not vpt.is_completed
        vpt.run()
        assert vpt.is_completed
        # Test the mean vibrational polarizability
        np.testing.assert_almost_equal(vpt.mean_polarizability,
                                       1.092296473682357e-08)
        # Changing the value of e_cut changes the value of the mean
        # vibrational polarizability
        vpt.e_cut = 0
        np.testing.assert_almost_equal(vpt.mean_polarizability,
                                       0.0007775548377767935)
        # Test that running the workflow again warns a UserWarning
        with pytest.warns(UserWarning):
            vpt.run()


class TestGeopt:

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_run(self):
        new_pos = Posinp([Atom('N', [0, 0, 0]), Atom('N', [0, 0, 1.1])],
                         units="angstroem", boundary_conditions="free")
        base_job = Job(posinp=new_pos, name="N2", run_dir="tests/geopt_N2")
        gwf = Geopt(base_job, maxrise=0.5)
        assert not gwf.is_completed
        gwf.run(nomp=3, nmpi=6)
        assert gwf.is_completed
        expected_pos = Posinp(
            [Atom('N', [-3.5879386957696453e-22, -2.564986669721281e-21,
                        0.0032486860088205526]),
             Atom('N', [2.5251356228246713e-22, 2.423609962870671e-21,
                        1.0967513378330371])],
            "angstroem", "free", cell=None)
        assert gwf.final_posinp == expected_pos
        # Test that running the workflow again warns a UserWarning
        with pytest.warns(UserWarning):
            gwf.run()

    def test_dry_run(self, dry_gwf):
        assert not dry_gwf.is_completed
        dry_gwf.run(nomp=3, nmpi=6, dry_run=True)
        assert not dry_gwf.is_completed

    @pytest.fixture
    def dry_gwf(self):
        new_pos = Posinp([Atom('N', [0, 0, 0]), Atom('N', [0, 0, 1.1])],
                         units="angstroem", boundary_conditions="free")
        base_job = Job(posinp=new_pos, name="N2", run_dir="tests/geopt_N2/dry")
        gwf = Geopt(base_job, maxrise=0.5)
        yield gwf
        with gwf.queue[0] as job:
            job.clean()
        os.rmdir(job.run_dir)


class TestDissociation:

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_run(self):
        frag1 = Posinp([Atom('N', [0.0, 0.0, 0.0])], units="angstroem",
                       boundary_conditions="free")
        frag2 = frag1
        distances = np.arange(0.95, 1.25, 0.05)
        dc = Dissociation(frag1, frag2, distances, name="N2",
                          run_dir="tests/dissociation_N2")
        assert not dc.is_completed
        dc.run(nmpi=6, nomp=3)
        assert dc.is_completed
        # The first job has the correct posinp
        atoms = [Atom('N', [0, 0, 0]), Atom('N', [0, 0.95, 0])]
        expected_pos = Posinp(
            atoms, units="angstroem", boundary_conditions="free")
        assert expected_pos == dc.queue[0].posinp
        # The correct minimum distance is found
        assert dc.minimum.distance == 1.1
        # The output energies are correct
        expected_energies = [
            -19.805444659275025, -19.85497382791818, -19.878933352041976,
            -19.884549270710195, -19.87716483741823, -19.86087438302968,
            -19.838574516454962
        ]
        np.testing.assert_array_almost_equal(dc.energies, expected_energies)
        # Test that running the workflow again warns a UserWarning
        with pytest.warns(UserWarning):
            dc.run()

    def test_init_raises_ValueError(self):
        frag1 = Posinp([Atom('N', [0.0, 0.0, 0.0])],
                       units="angstroem", boundary_conditions="free")
        frag2 = Posinp([Atom('N', [0.0, 0.0, 0.0])], cell=[8, 8, 8],
                       units="angstroem", boundary_conditions="periodic")
        distances = np.arange(0.95, 1.25, 0.05)
        with pytest.raises(ValueError):
            Dissociation(frag1, frag2, distances)
