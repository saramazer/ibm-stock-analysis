import os
from writerai import Writer

client = Writer(
    # This is the default and can be omitted
    api_key=os.environ.get("WRITER_API_KEY"),
)
model = client.models.list()
print(model.models)
