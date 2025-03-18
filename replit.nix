{pkgs}: {
  deps = [
    pkgs.github-runner
    pkgs.zlib
    pkgs.xcodebuild
    pkgs.glibcLocales
    pkgs.portmidi
    pkgs.pkg-config
    pkgs.libpng
    pkgs.libjpeg
    pkgs.freetype
    pkgs.fontconfig
    pkgs.SDL2_ttf
    pkgs.SDL2_mixer
    pkgs.SDL2_image
    pkgs.SDL2
  ];
}
