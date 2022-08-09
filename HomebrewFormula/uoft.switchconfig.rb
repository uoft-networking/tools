# Documentation: https://docs.brew.sh/Formula-Cookbook
#                https://rubydoc.brew.sh/Formula
# PLEASE REMOVE ALL GENERATED COMMENTS BEFORE SUBMITTING YOUR PULL REQUEST!
class UofTSwitchconfig < Formula

  desc ""
  homepage "https://github.com/uoft-networking/tools/tree/main/projects/switchconfig"
  url "https://files.pythonhosted.org/packages/9a/a7/19f48560c68099cdf0b42b74a286a331a9a0f46a99298ab0ea260b4849cf/uoft_switchconfig-0.2.2-py3-none-any.whl"
  sha256 "9a5ed11c64bb374a8339aaa9fdc5290cbb8a4e58c475bdfa45ee84afcf3f4c96"
  license "MIT"

  depends_on "python@3.10"
  depends_on "pipx" => :build
  depends_on "rust" => :build

  def install
    # ENV.deparallelize  # if your formula fails when building in parallel
    ENV["PIPX_HOME"] = prefix
    ENV["PIPX_BIN_DIR"] = bin
    ENV["PIPX_DEFAULT_PYTHON"] = Formula["python@3.10"].opt_bin/"python3"

    system "pipx install ./*.whl"

    (bash_completion/"uoft_switchconfig").write `#{bin}/uoft_switchconfig --show-completion bash`
    (fish_completion/"uoft_switchconfig.fish").write `#{bin}/uoft_switchconfig --show-completion fish`
    (zsh_completion/"_uoft_switchconfig").write `#{bin}/uoft_switchconfig --show-completion zsh`
  end

  test do
    # `test do` will create, run in and delete a temporary directory.
    #
    # This test will fail and we won't accept that! For Homebrew/homebrew-core
    # this will need to be a test that verifies the functionality of the
    # software. Run the test with `brew test uoft_switchconfig`. Options passed
    # to `brew install` such as `--HEAD` also need to be provided to `brew test`.
    #
    # The installed folder is not in the path, so use the entire path to any
    # executables being tested: `system "#{bin}/program", "do", "something"`.
    system "#{bin}/uoft_switchconfig", "--help"
  end
end
