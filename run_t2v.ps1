$Prompt = @"
Luxury cinematic product commercial. A premium crystal perfume bottle stands
on flowing black silk in an elegant dark studio. Warm golden rim lighting,
realistic glass reflections and refractions, tiny golden particles floating
slowly through the air. Extremely smooth slow cinematic dolly-in, subtle
parallax, shallow depth of field, rich blacks, detailed highlights,
photorealistic materials, professional studio lighting, stable geometry,
strong temporal consistency, realistic motion, premium advertising aesthetic.
No text, no logo, no watermark, no flickering, no distortion.
Soft luxurious atmospheric orchestral ambience.
"@


# ------------------------------------------------
# VIDEO QUALITY
# RTX 3070 8GB recommended HQ profile
# ------------------------------------------------

$W      = 640
$H      = 384

# Valid H3 frames:
# 5, 22, 39, 56, 73, 90, 107, 124...
$Frames = 56

$FPS    = 24

# 20 = HQ
# 30 = slower / possibly slightly better
$Steps  = 20

$Seed   = 106


# ------------------------------------------------
# OUTPUT
# ------------------------------------------------

$Out = "minimax_h3_HQ.webm"


# ------------------------------------------------
# OPTIONAL IMAGE-TO-VIDEO
#
# Để trống = Text-to-Video
#
# Ví dụ:
# $InitImg = "G:\minimax-h3\input\first_frame.jpg"
# ------------------------------------------------

$InitImg = ""


# ================================================================
# PATHS
# ================================================================

$root = "G:\minimax-h3"

$models = Join-Path $root "models"

$outputDir = Join-Path $root "outputs"


# ================================================================
# FIND SD-CLI
# ================================================================

$bin = Get-ChildItem `
    "$root\bin" `
    -Recurse `
    -Filter "sd-cli.exe" `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName


# ================================================================
# MODELS
# ================================================================

$dit = Join-Path `
    $models `
    "minimax_h3_fl2va_pruned-UD-Q2_K_XL.gguf"


$llm = Join-Path `
    $models `
    "qwen3vl_32b_minimax_h3-Q2_K_M.gguf"


$vae = Join-Path `
    $models `
    "vae\minimax_h3_video_vae_fp16.safetensors"


$avae = Join-Path `
    $models `
    "vae\minimax_h3_audio_vae_fp32.safetensors"


# ================================================================
# CREATE OUTPUT DIR
# ================================================================

if (-not (Test-Path $outputDir)) {

    New-Item `
        -ItemType Directory `
        -Path $outputDir `
        -Force |
        Out-Null
}


# ================================================================
# CHECK REQUIRED FILES
# ================================================================

$requiredFiles = @(

    @{
        Name = "sd-cli"
        Path = $bin
    },

    @{
        Name = "DiT"
        Path = $dit
    },

    @{
        Name = "LLM"
        Path = $llm
    },

    @{
        Name = "Video VAE"
        Path = $vae
    },

    @{
        Name = "Audio VAE"
        Path = $avae
    }
)


foreach ($item in $requiredFiles) {

    if (
        -not $item.Path -or
        -not (Test-Path $item.Path)
    ) {

        Write-Host ""
        Write-Host "ERROR: Missing $($item.Name)" `
            -ForegroundColor Red

        Write-Host "Path:"
        Write-Host "  $($item.Path)"

        exit 1
    }
}


# ================================================================
# VALIDATE H3 FRAMES
# ================================================================

if (
    $Frames -lt 5 -or
    (($Frames - 5) % 17 -ne 0)
) {

    if ($Frames -lt 5) {

        $Frames = 5

    }
    else {

        $k = [Math]::Ceiling(
            ($Frames - 5) / 17.0
        )

        $Frames = [int](
            17 * $k + 5
        )
    }


    Write-Host (
        "Frame count automatically aligned to: $Frames"
    ) -ForegroundColor Yellow
}


# ================================================================
# INIT IMAGE CHECK
# ================================================================

if ($InitImg) {

    if (-not (Test-Path $InitImg)) {

        Write-Host ""
        Write-Host "ERROR: Init image not found:" `
            -ForegroundColor Red

        Write-Host $InitImg

        exit 1
    }

    $InitImg = (
        Resolve-Path $InitImg
    ).Path
}


# ================================================================
# OUTPUT
# ================================================================

$outputPath = Join-Path `
    $outputDir `
    $Out


# Delete previous output with same name

if (Test-Path $outputPath) {

    Remove-Item `
        $outputPath `
        -Force
}


# ================================================================
# SD-CLI ARGUMENTS
# ================================================================

$cliArgs = @(

    # MODE
    "-M",
    "vid_gen",


    # MODELS
    "--diffusion-model",
    $dit,

    "--llm",
    $llm,

    "--vae",
    $vae,

    "--audio-vae",
    $avae,


    # PROMPT
    "-p",
    $Prompt,


    # VIDEO
    "-W",
    "$W",

    "-H",
    "$H",

    "--video-frames",
    "$Frames",

    "--fps",
    "$FPS",


    # SAMPLING
    "--steps",
    "$Steps",


    # MiniMax-H3 CFG-free
    "--cfg-scale",
    "1.0",


    "--seed",
    "$Seed",


    # ============================================================
    # RTX 3070 8GB OPTIMIZATION
    # ============================================================

    # Flash Attention
    "--diffusion-fa",


    # Stream/offload DiT weights through RAM
    "--offload-to-cpu",


    # Keep Qwen3-VL text encoder on CPU
    "--backend",
    "te=cpu",


    # Reduce VAE VRAM requirement
    "--vae-tiling",


    # Reduce temporal decode memory
    "--temporal-tiling",


    # Keep RNG on CPU
    "--rng",
    "cpu",


    # OUTPUT
    "-o",
    $outputPath,


    # VERBOSE
    "-v"
)


# ================================================================
# IMAGE TO VIDEO
# ================================================================

if ($InitImg) {

    $cliArgs += @(

        "-i",
        $InitImg
    )
}


# ================================================================
# SHOW SETTINGS
# ================================================================

$duration = (
    $Frames / [double]$FPS
)


Write-Host ""
Write-Host "============================================================"
Write-Host " MiniMax-H3 - RTX 3070 8GB"
Write-Host "============================================================"

Write-Host ""

Write-Host "Resolution : ${W}x${H}"
Write-Host "Frames     : $Frames"
Write-Host "FPS        : $FPS"

Write-Host (
    "Duration   : {0:N2} sec" -f $duration
)

Write-Host "Steps      : $Steps"
Write-Host "CFG        : 1.0"
Write-Host "Seed       : $Seed"

Write-Host ""

Write-Host "GPU profile:"
Write-Host "  Flash Attention : ON"
Write-Host "  CPU Offload     : ON"
Write-Host "  Text Encoder    : CPU"
Write-Host "  VAE Tiling      : ON"
Write-Host "  Temporal Tiling : ON"
Write-Host "  RNG             : CPU"

Write-Host ""

Write-Host "Output:"
Write-Host "  $outputPath"

Write-Host ""

Write-Host "Prompt:"
Write-Host "------------------------------------------------------------"
Write-Host $Prompt
Write-Host "------------------------------------------------------------"

Write-Host ""
Write-Host "Starting..."
Write-Host ""


# ================================================================
# RUN
#
# Không có HTTP timeout.
# PowerShell sẽ đợi sd-cli cho đến khi xong hoặc process crash.
# ================================================================

$sw = [Diagnostics.Stopwatch]::StartNew()


& $bin @cliArgs


$exitCode = $LASTEXITCODE


$sw.Stop()


# ================================================================
# RESULT
# ================================================================

Write-Host ""
Write-Host "============================================================"


if (
    $exitCode -eq 0 -and
    (Test-Path $outputPath)
) {

    $file = Get-Item $outputPath

    $sizeMB = (
        $file.Length / 1MB
    )


    Write-Host " GENERATION COMPLETE" `
        -ForegroundColor Green

    Write-Host "============================================================"

    Write-Host ""

    Write-Host (
        "Time   : {0:N0} sec ({1:N2} min)" -f `
        $sw.Elapsed.TotalSeconds,
        $sw.Elapsed.TotalMinutes
    )

    Write-Host (
        "Size   : {0:N2} MB" -f $sizeMB
    )

    Write-Host ""

    Write-Host "Output:"
    Write-Host "  $outputPath"

}
else {

    Write-Host " GENERATION FAILED" `
        -ForegroundColor Red

    Write-Host "============================================================"

    Write-Host ""

    Write-Host "Exit code:"
    Write-Host "  $exitCode"

    Write-Host ""

    Write-Host (
        "Elapsed: {0:N0} sec" -f `
        $sw.Elapsed.TotalSeconds
    )

    Write-Host ""

    Write-Host "Nếu CUDA OOM, giảm config thành:" `
        -ForegroundColor Yellow

    Write-Host ""
    Write-Host '  $Frames = 39'
    Write-Host '  $Steps  = 20'

    Write-Host ""

    exit $exitCode
}

