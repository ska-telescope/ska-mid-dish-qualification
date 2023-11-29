[[ -s pyproject.toml ]] && {
    rm pyproject.toml;
    ln -s pyproject_for_poetry.toml pyproject.toml; 
}
