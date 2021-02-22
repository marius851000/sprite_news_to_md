{ pkgs ? import <nixpkgs> {}}:

pkgs.mkShell {
    name = "sprite_news_to_md";

    propagatedBuildInputs = [ pkgs.python3Packages.GitPython ];
}

#TODO: try the nix flake method