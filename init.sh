#!/bin/bash

# This file contains any project specific shell commands that are needed to set up a working local dev environment
# for this project. It is used by the overall init.sh script in https://gitlab.holi.team/app/holi-meta 

# install the Python virtualenv
pyenv install -s "$(cat .python-version)"
pyenv local "$(cat .python-version)"
# now, reinitialize via direnv (first run in checkoutAndPrepare did not succeed due to missing python interpreter)
direnv reload
# we need to install some postgis libs for holi-okuna
brewInstall gdal
brewInstall proj
brewInstall geos
if [[ -f /opt/homebrew/lib/libgdal.dylib && -f /opt/homebrew/lib/libgeos_c.dylib && -f /opt/homebrew/lib/libproj.dylib ]]; then
  # MacOS
  [[ -f .envrc.local ]] || cat <<- EOF > .envrc.local
export GDAL_LIBRARY_PATH=/opt/homebrew/lib/libgdal.dylib
export GEOS_LIBRARY_PATH=/opt/homebrew/lib/libgeos_c.dylib
export PROJ_LIBRARY_PATH=/opt/homebrew/lib/libproj.dylib
EOF
  # since we just created the .envrc.local file, the autogeneration from template in holi-okuna won't work anymore, so we need to do it here
  cat .envrc.local.template >> .envrc.local
elif [[ -f /home/linuxbrew/.linuxbrew/lib/libgdal.so && -f /home/linuxbrew/.linuxbrew/lib/libgeos_c.so && -f /home/linuxbrew/.linuxbrew/lib/libproj.so ]]; then
  # Linux
  [[ -f .envrc.local ]] || cat <<- EOF > .envrc.local
export GDAL_LIBRARY_PATH=/home/linuxbrew/.linuxbrew/lib/libgdal.so
export GEOS_LIBRARY_PATH=/home/linuxbrew/.linuxbrew/lib/libgeos_c.so
export PROJ_LIBRARY_PATH=/home/linuxbrew/.linuxbrew/lib/libproj.so
# if not exported like this, system libs will be used as deps of brew libs
export LD_LIBRARY_PATH=/home/linuxbrew/.linuxbrew/lib/:\$LD_LIBRARY_PATH
EOF
  # since we just created the .envrc.local file, the autogeneration from template in holi-okuna won't work anymore, so we need to do it here
  cat .envrc.local.template >> .envrc.local
else
  fail "Could not determine how to include the libraries necessary for PostGIS. Please investigate in init.sh."
fi
