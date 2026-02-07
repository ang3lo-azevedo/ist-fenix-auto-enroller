{
  description = "IST Fenix Auto Enroller by nos4a2 (Ângelo Azevedo)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      
      pythonEnv = pkgs.python311.withPackages (ps: with ps; [
        selenium
        tkinter
        requests
        beautifulsoup4
      ]);
      
    in {
      packages.${system}.default = pkgs.stdenv.mkDerivation {
        name = "ist-fenix-auto-enroller";
        src = ./.;
        
        buildInputs = [ pythonEnv ];
        
        installPhase = ''
          mkdir -p $out/bin $out/app
          cp -r main.py src/ $out/app/
          
          cat > $out/bin/ist-fenix-auto-enroller << EOL
          #!/bin/sh
          cd $out/app
          export CHROME_BIN="${pkgs.chromium}/bin/chromium"
          export CHROMEDRIVER_PATH="${pkgs.chromedriver}/bin/chromedriver"
          exec ${pythonEnv}/bin/python main.py
          EOL
          
          chmod +x $out/bin/ist-fenix-auto-enroller
        '';
      };

      apps.${system}.default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/ist-fenix-auto-enroller";
      };

      devShells.${system}.default = pkgs.mkShell {
        buildInputs = [
          pythonEnv
          pkgs.chromium
          pkgs.chromedriver
        ];
        
        shellHook = ''
          export CHROME_BIN="${pkgs.chromium}/bin/chromium"
          export CHROMEDRIVER_PATH="${pkgs.chromedriver}/bin/chromedriver"
          export PATH="${pkgs.chromedriver}/bin:$PATH"
        '';
      };
    };
}
