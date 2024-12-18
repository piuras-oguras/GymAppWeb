# Funkcja pomocnicza do budowania URL z parametrami


def build_ssrs_url(report_path: str, params: dict) -> str:
    query_params = {
        "Rpt": report_path,
        "rs:Command": "Render",
        "rs:Format": "HTML4.0"
    }
    # Dodaj parametry raportu
    query_params.update(params)
    return f"{SSRS_BASE_URL}?{urlencode(query_params)}"