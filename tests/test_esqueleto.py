from focus_ipca import exportar, extrair, transformar


def test_modulos_de_focus_ipca_sao_importaveis():
    assert extrair.main is not None
    assert transformar.main is not None
    assert exportar.main is not None