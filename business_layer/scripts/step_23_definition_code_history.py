"""Committed, service-only demonstration of definition source control."""
from ._common import run, find_model, expect_error

CODE = '''class Note(Entity):
    text: String(nullable=False)
'''


async def main(business, key):
    """Save, compare, restore and execute definition code; keep all effects."""
    history_key = key + '_code_history'
    model = await find_model(business, history_key)
    if model is None:
        model = await business.entities.create_model(history_key, 'Definition code history')
    helper = business.definition_code
    head = await helper.get_version(model.id)
    first = await helper.save(model.id, CODE, reason='Initial source',
                              expected_version=head.version if head else 0)
    second = await helper.save(model.id, CODE + '# Editor comment\n', reason='Source-only edit',
                               expected_version=first.version)
    assert second.version == first.version + 1
    assert (await helper.save(model.id, second.code)).id == second.id
    difference = await helper.diff(model.id, first.version, second.version)
    assert '+# Editor comment' in difference
    conflict = await expect_error('stale source version', helper.save(
        model.id, CODE, expected_version=first.version), 409)
    restored = await helper.restore(model.id, first.version, expected_version=second.version)
    assert restored.version == second.version + 1
    applied = await business.execute(model.id, code=restored.code)
    assert applied.code_version is not None
    first_object = await business.execute(model.id, code=CODE + 'note = Note(text="hello")\n')
    next_object = await business.execute(model.id, code=CODE + 'note = Note(text="hello")\n')
    assert first_object.objects['note'] != next_object.objects['note']
    assert not next_object.schema_changed
    assert first_object.code_version == next_object.code_version
    latest = await helper.get_version(model.id)
    assert latest.schema_revision_id == next_object.revision_id
    count_before = len(await helper.list_versions(model.id))
    try:
        await helper.save(model.id, 'invalid source @')
    except Exception as error:
        if not isinstance(error, (ValueError, SyntaxError)):
            from fastapi import HTTPException
            if not isinstance(error, HTTPException):
                raise
    else:
        raise AssertionError('Invalid code was accepted')
    assert len(await helper.list_versions(model.id)) == count_before
    return {'model_id': model.id, 'source_versions': count_before,
            'diff': difference, 'conflict': conflict,
            'restored_version': restored.version,
            'latest_code_version': latest.version,
            'objects_created': [first_object.objects, next_object.objects]}


if __name__ == '__main__':
    run(main)
