if [ -s pyproject.toml ]; then
    rm pyproject.toml;
    ln -s pyproject_for_poetry.toml pyproject.toml; 
fi
