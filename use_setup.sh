if [ -s pyproject.toml ]; then
    rm pyproject.toml;
    ln -s pyproject_for_setup.toml pyproject.toml; 
fi
