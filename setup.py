import os
import shutil
import subprocess
from pathlib import Path
from setuptools import setup
from torch.utils.cpp_extension import CUDAExtension, BuildExtension


# Determine the OptiX SDK path
# If there is a optix directory in the `third_party` directory, use it as the OptiX SDK path
# Otherwise, use the environment variable `OPTIX_HOME`
# If both are not set, raise an error
OPTIX_HOME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "third_party/optix")
if not os.path.exists(OPTIX_HOME):
    OPTIX_HOME = os.environ.get('OPTIX_HOME')
    if OPTIX_HOME is None or not os.path.exists(OPTIX_HOME):
        raise ValueError("Please set the OPTIX_HOME environment variable to the path to the OptiX SDK")
OPTIX_HOME = os.path.join(OPTIX_HOME, "include")
print(f"Using OptiX SDK at {OPTIX_HOME}")


# Custom build extension to build the OptiX tracing kernel
class CustomBuildExtension(BuildExtension):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def build_extensions(self):
        # Record the python package source directory
        pkg_source = Path(__file__).resolve().parent

        # Run the original build_extensions
        super().build_extensions()

        # Propagate CMake failures instead of reporting an incomplete install.
        cmake_build = Path(self.build_temp).resolve() / 'optix'
        subprocess.run([
            'cmake', '-S', str(pkg_source), '-B', str(cmake_build),
            f'-DOPTIX_HOME={Path(OPTIX_HOME).parent}',
        ], check=True)
        subprocess.run(['cmake', '--build', str(cmake_build)], check=True)

        # Put runtime kernels in the build output so they are included in the
        # wheel, rather than writing directly into the build user's site-packages.
        pkg_target = Path(self.get_ext_fullpath('diff_surfel_tracing._C')).parent
        pkg_target.mkdir(parents=True, exist_ok=True)
        for name in ('forward.ptx', 'backward.ptx'):
            kernel = cmake_build / 'ptx' / name
            if not kernel.is_file() or kernel.stat().st_size == 0:
                raise RuntimeError(f'OptiX build did not produce {kernel}')
            shutil.copy2(kernel, pkg_target / name)


# Setup for the python package
setup(
    name="diff_surfel_tracing",
    packages=['diff_surfel_tracing'],
    package_data={'diff_surfel_tracing': ['*.ptx']},
    version='0.0.1',
    ext_modules=[
        CUDAExtension(
            name="diff_surfel_tracing._C",
            sources=[
                "optix_tracer/common.cpp",
                "optix_tracer/optix_wrapper.cpp",
                "trace_surfels.cpp",
                "ext.cpp"
            ],
            # extra_compile_args={"nvcc": ["-I" + os.path.join(os.path.dirname(os.path.abspath(__file__)), "third_party/glm/")]},
            include_dirs=[OPTIX_HOME]
        ),
    ],
    cmdclass={
        'build_ext': CustomBuildExtension
    }
)
