// Central Engine: CLI, policies and identity by Central IA Studio contributors.
// MIT License. Inference/server implementation: llama.cpp / ggml authors (MIT).
#include <filesystem>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>
#include <utility>
#include <clocale>
#include <algorithm>
#include <cctype>

int llama_server(int argc, char ** argv);

static int integer(const std::string & text, int min, int max) {
    size_t end = 0;
    int n = std::stoi(text, &end);
    if (end != text.size() || n < min || n > max) throw std::invalid_argument("valor numerico fora do intervalo");
    return n;
}

static int central_main(int argc, char ** argv) {
    std::setlocale(LC_NUMERIC, "C");
    try {
        std::map<std::string,std::string> p = {{"--host","127.0.0.1"},{"--port","5001"},{"--contextsize","4096"},
            {"--threads","2"},{"--blasthreads","2"},{"--blasbatchsize","128"},{"--gpulayers","0"},{"--quantkv","q8_0"},{"--prompt-cache-mib","256"}};
        bool flash = true;
        for (int i=1; i<argc; ++i) {
            std::string key = argv[i];
            if (key == "--help" || key == "-h") {
                std::cout << "Central Engine 0.2.0 - motor local de inferencia CPU\n"
                    "Base: llama.cpp / ggml (MIT). Binario x64 AVX2, sem CUDA.\n"
                    "Uso: central-engine-nocuda --model MODELO.gguf [opcoes]\n"
                    "--port 5001 --contextsize 4096 --threads 2 --blasthreads 2\n"
                    "--blasbatchsize 128 --quantkv f16|bf16|q8_0|q5_1|q4_0\n"
                    "--jinjatemplate ARQUIVO.jinja --noflashattention\n"
                    "--prompt-cache-mib 256 (0 desativa snapshots adicionais em RAM)\n"
                    "--host aceita somente 127.0.0.1. --gpulayers aceita somente 0.\n"
                    "Nao baixa modelos nem executa ferramentas. Ctrl+C encerra.\n";
                return 0;
            }
            if (key == "--version" || key == "--diagnostico") {
                std::cout << R"({"engine":"CentralEngine","version":"0.2.0","cpu_only":true,"isa":"AVX2","upstream":"llama.cpp","commit":"d1044bc82712fbf08996080bef6298b24a27e9c7"})" << '\n';
                return 0;
            }
            if (key == "--jinja") continue;
            if (key == "--noflashattention") { flash = false; continue; }
            if (!p.count(key) && key != "--model" && key != "--jinjatemplate") throw std::invalid_argument("opcao desconhecida: "+key);
            if (++i >= argc) throw std::invalid_argument("valor ausente: "+key);
            p[key] = argv[i];
        }
        if (p["--host"] != "127.0.0.1") throw std::invalid_argument("acesso remoto desativado; use 127.0.0.1");
        if (integer(p["--gpulayers"],0,0) != 0) return 2;
        integer(p["--port"],1024,65535); integer(p["--contextsize"],256,524288);
        integer(p["--threads"],1,256); integer(p["--blasthreads"],1,256);
        integer(p["--prompt-cache-mib"],0,8192);
        const int batch = integer(p["--blasbatchsize"],16,4096);
        if (batch & (batch-1)) throw std::invalid_argument("lote deve ser potencia de dois entre 16 e 4096");
        auto model = std::filesystem::u8path(p["--model"]);
        std::string extension = model.extension().u8string();
        std::transform(extension.begin(),extension.end(),extension.begin(),[](unsigned char c){return std::tolower(c);});
        if (extension != ".gguf" || !std::filesystem::is_regular_file(model)) throw std::invalid_argument("informe um GGUF local existente em --model");
        const std::string kv = p["--quantkv"];
        if (kv != "f16" && kv != "bf16" && kv != "q8_0" && kv != "q5_1" && kv != "q4_0") throw std::invalid_argument("cache KV nao suportado");
        // Quantized V cache requires Flash Attention; reject instead of silently ignoring it.
        if (!flash && kv != "f16" && kv != "bf16") throw std::invalid_argument("cache KV quantizado exige Flash Attention; selecione f16 com FA desligada");
        std::vector<std::string> args = {"central-engine-nocuda", "--model",p["--model"],"--host","127.0.0.1", "--port",p["--port"],
            "--ctx-size",p["--contextsize"],"--threads",p["--threads"],"--threads-batch",p["--blasthreads"],
            "--batch-size",p["--blasbatchsize"],"--ubatch-size",p["--blasbatchsize"],"--gpu-layers","0",
            "--cache-type-k",kv,"--cache-type-v",kv,"--flash-attn",flash?"on":"off","--parallel","1",
            "--cache-ram",p["--prompt-cache-mib"],"--cache-prompt","--no-context-shift",
            "--fit","off","--jinja","--offline","--no-webui","--no-ui-mcp-proxy","--reasoning-format","deepseek",
            "--cors-origins","http://127.0.0.1:0"};
        if (p.count("--jinjatemplate")) {
            auto path = std::filesystem::u8path(p["--jinjatemplate"]);
            if (!std::filesystem::is_regular_file(path) || std::filesystem::file_size(path)>1048576 ||
                (path.extension()!=".jinja" && path.extension()!=".j2")) throw std::invalid_argument("template deve ser .jinja/.j2 local de ate 1 MiB");
            args.insert(args.end(),{"--chat-template-file",p["--jinjatemplate"]});
        }
        std::cerr << "Central Engine 0.2.0 | CPU AVX2 | llama.cpp MIT | apenas 127.0.0.1\n";
        std::vector<char*> raw;
        for (auto & arg : args) raw.push_back(arg.data());
        return llama_server(static_cast<int>(raw.size()), raw.data());
    } catch (const std::exception & e) {
        std::cerr << "Central Engine: " << e.what() << '\n';
        return 2;
    }
}

#ifdef _WIN32
#include <windows.h>
int wmain(int argc, wchar_t ** argv) {
    std::vector<std::string> args;
    for (int i=0; i<argc; ++i) {
        const int size = WideCharToMultiByte(CP_UTF8,0,argv[i],-1,nullptr,0,nullptr,nullptr);
        if (!size) return 2;
        std::string text(size,'\0');
        WideCharToMultiByte(CP_UTF8,0,argv[i],-1,text.data(),size,nullptr,nullptr);
        text.pop_back(); args.push_back(std::move(text));
    }
    std::vector<char*> raw;
    for (auto & text : args) raw.push_back(text.data());
    return central_main(argc, raw.data());
}
#else
int main(int argc, char ** argv) { return central_main(argc,argv); }
#endif
