import os
import uuid
import pytest
from windows_io import single_instance


@pytest.mark.skipif(os.name != "nt", reason="Windows named mutex")
def test_duplicate_instance_is_rejected_until_first_instance_exits():
    name = "Local\\CopyThatTest_" + uuid.uuid4().hex
    with single_instance(name) as first:
        assert first
        with single_instance(name) as second:
            assert not second
    with single_instance(name) as restarted:
        assert restarted
