// Central Engine additions, MIT. Upstream server remains copyright ggml authors.
#pragma once
static server_http_context::handler_t ex_wrapper(server_http_context::handler_t func);

static void central_register_routes(server_http_context & http, server_routes & routes) {
    http.get("/api/extra/version", [](const server_http_req &) -> server_http_res_ptr {
        auto res = std::make_unique<server_http_res>();
        res->data = R"({"result":"CentralEngine","version":"0.3.0","protocol":1,"jinja":true,"llm":true,"cpu_only":true,"upstream":"llama.cpp","upstream_commit":"d1044bc82712fbf08996080bef6298b24a27e9c7","abort":"disconnect","telemetry":false,"prompt_cache_control":true,"context_shift":false})";
        return res;
    });
    auto props = routes.get_props;
    http.get("/central/v1/status", ex_wrapper([props](const server_http_req & req) -> server_http_res_ptr {
        auto res = props(req);
        if (res->status == 200) {
            auto data = json::parse(res->data);
            res->data = json({{"engine","CentralEngine"},{"version","0.3.0"},{"cpu_only",true},
                {"model",data.at("model_alias")},{"context",data.at("default_generation_settings").at("n_ctx")},
                {"upstream_commit","d1044bc82712fbf08996080bef6298b24a27e9c7"}}).dump();
        }
        return res;
    }));
    http.get("/api/v1/model", ex_wrapper([props](const server_http_req & req) -> server_http_res_ptr {
        auto res = props(req);
        if (res->status == 200) {
            auto data = json::parse(res->data);
            res->data = json({{"result",data.at("model_alias")}}).dump();
        }
        return res;
    }));
    http.get("/api/extra/true_max_context_length", ex_wrapper([props](const server_http_req & req) -> server_http_res_ptr {
        auto res = props(req);
        if (res->status == 200) {
            auto data = json::parse(res->data);
            res->data = json({{"value",data.at("default_generation_settings").at("n_ctx")}}).dump();
        }
        return res;
    }));
    auto count = routes.post_chat_completions_tok;
    http.post("/api/extra/tokencount", ex_wrapper([count](const server_http_req & req) -> server_http_res_ptr {
        auto res = count(req);
        if (res->status == 200) {
            auto data = json::parse(res->data);
            res->data = json({{"value",data.at("input_tokens")}}).dump();
        }
        return res;
    }));
}
