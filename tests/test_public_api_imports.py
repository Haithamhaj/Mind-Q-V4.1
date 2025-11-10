"""Ensure new public API surfaces remain importable."""

def test_public_modules_exist() -> None:
    import backend.src.app.pipeline_api as pipeline_module
    import backend.src.app.services.business_validation as bv_module
    import backend.src.app.services.run_history as rh_module

    assert hasattr(pipeline_module, "run_pipeline")
    assert hasattr(bv_module, "run_business_validation")
    assert hasattr(rh_module, "purge_run_history")
