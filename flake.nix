{
  description = "inCalc terminal toolbox";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.python3Packages.buildPythonApplication {
            pname = "incalc";
            version = "0.1.0";
            pyproject = true;
            src = self;

            build-system = [ pkgs.python3Packages.hatchling ];
            pythonImportsCheck = [ "incalc" "incalc.app" ];

            meta = {
              description = "Terminal toolbox for personal calculations";
              mainProgram = "incalc";
            };
          };
        });
    };
}
