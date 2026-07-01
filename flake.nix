{
  description = "IST Fenix Auto Enroller by nos4a2 (Ângelo Azevedo)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      # NixOS runs on these Linux architectures; the app is a Tk GUI that
      # drives chromium, so we intentionally only target Linux.
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];

      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      pkgsFor = system: nixpkgs.legacyPackages.${system};

      mkPackage = pkgs:
        let
          pythonEnv = pkgs.python311.withPackages (ps: with ps; [
            selenium
            tkinter
            requests
            beautifulsoup4
          ]);

          desktopItem = pkgs.makeDesktopItem {
            name = "ist-fenix-auto-enroller";
            desktopName = "IST Fénix Auto Enroller";
            comment = "Automatically enroll in IST Fénix shifts";
            exec = "ist-fenix-auto-enroller";
            icon = "ist-fenix-auto-enroller";
            categories = [ "Education" ];
            terminal = false;
            # The Tk window reports WM_CLASS "Tk"; this lets the launcher
            # associate the running window with this menu entry.
            startupWMClass = "Tk";
          };
        in
        pkgs.stdenv.mkDerivation {
          pname = "ist-fenix-auto-enroller";
          version = "1.0.0";
          src = ./.;

          nativeBuildInputs = [
            pkgs.makeWrapper
            pkgs.copyDesktopItems
            pkgs.librsvg
          ];

          # copyDesktopItems (runs in postInstall) installs this into
          # $out/share/applications so it shows up in the application menu.
          desktopItems = [ desktopItem ];

          # Nothing to build; just stage the sources and wrap the interpreter.
          dontConfigure = true;
          dontBuild = true;

          installPhase = ''
            runHook preInstall

            appdir="$out/share/ist-fenix-auto-enroller"
            mkdir -p "$appdir"
            cp -r main.py src "$appdir"/

            # Running python with an absolute path to main.py puts main.py's
            # directory on sys.path, so `from src.gui import GUI` resolves
            # without cd-ing into the (read-only) store. chromium/chromedriver
            # are pinned via env vars the bot reads at runtime.
            makeWrapper ${pythonEnv}/bin/python "$out/bin/ist-fenix-auto-enroller" \
              --add-flags "$appdir/main.py" \
              --set CHROME_BIN ${pkgs.chromium}/bin/chromium \
              --set CHROMEDRIVER_PATH ${pkgs.chromedriver}/bin/chromedriver \
              --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.chromium pkgs.chromedriver ]}

            # Install the app icon: scalable SVG + rasterized PNG sizes so it
            # renders crisply everywhere in the application menu / taskbar.
            install -Dm644 assets/icon.svg \
              "$out/share/icons/hicolor/scalable/apps/ist-fenix-auto-enroller.svg"
            for size in 32 48 64 128 256; do
              mkdir -p "$out/share/icons/hicolor/''${size}x''${size}/apps"
              rsvg-convert -w "$size" -h "$size" assets/icon.svg \
                -o "$out/share/icons/hicolor/''${size}x''${size}/apps/ist-fenix-auto-enroller.png"
            done

            runHook postInstall
          '';

          meta = with pkgs.lib; {
            description = "Automatically enroll in IST Fénix shifts";
            homepage = "https://github.com/ang3lo-azevedo/ist-fenix-auto-enroller";
            license = licenses.mit;
            platforms = supportedSystems;
            mainProgram = "ist-fenix-auto-enroller";
          };
        };

      mkDevShell = pkgs:
        let
          pythonEnv = pkgs.python311.withPackages (ps: with ps; [
            selenium
            tkinter
            requests
            beautifulsoup4
          ]);
        in
        pkgs.mkShell {
          packages = [
            pythonEnv
            pkgs.chromium
            pkgs.chromedriver
          ];

          shellHook = ''
            export CHROME_BIN="${pkgs.chromium}/bin/chromium"
            export CHROMEDRIVER_PATH="${pkgs.chromedriver}/bin/chromedriver"
          '';
        };
    in
    {
      packages = forAllSystems (system: {
        default = mkPackage (pkgsFor system);
        ist-fenix-auto-enroller = mkPackage (pkgsFor system);
      });

      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/ist-fenix-auto-enroller";
        };
      });

      devShells = forAllSystems (system: {
        default = mkDevShell (pkgsFor system);
      });

      formatter = forAllSystems (system: (pkgsFor system).nixpkgs-fmt);

      # Lets other flakes/NixOS configs pull the package in via an overlay:
      #   nixpkgs.overlays = [ inputs.ist-fenix-auto-enroller.overlays.default ];
      #   environment.systemPackages = [ pkgs.ist-fenix-auto-enroller ];
      overlays.default = final: prev: {
        ist-fenix-auto-enroller = mkPackage final;
      };
    };
}
