[[ -s pyproject.toml ]] && {
    rm pyproject.toml;
    ln -s pyproject_for_setup.toml pyproject.toml; 
}
