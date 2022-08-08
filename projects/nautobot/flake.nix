{
  description = "UofT Nautobot Plugin";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs";

  outputs = { self, nixpkgs, flake-utils }:
    (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        mypython = pkgs.python310.withPackages (p: [
              
            ]);
      in
      {

        defaultPackage = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          python = mypython;
        };

        devShell = pkgs.mkShell {
          buildInputs = [ mypython];
        };
      }));
}
