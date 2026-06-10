using System.Text.Json;
using PptAgentStudio_App.Services;

namespace PptAgentStudio.App.Tests;

[TestClass]
public sealed class RuntimeToolCatalogSummaryTests
{
    [TestMethod]
    public void FromPayloadReadsToolNamesWithoutSchemaNoise()
    {
        using var document = JsonDocument.Parse(
            """
            {
              "tools": [
                {
                  "name": "deck.create_from_outline",
                  "description": "Create a deck.",
                  "input_schema": { "type": "object" }
                },
                {
                  "name": "pptx.export",
                  "description": "Export a deck.",
                  "input_schema": { "type": "object" }
                }
              ]
            }
            """);

        var summary = RuntimeToolCatalogSummary.FromPayload(document.RootElement);

        Assert.AreEqual(2, summary.ToolCount);
        CollectionAssert.AreEqual(
            new[] { "deck.create_from_outline", "pptx.export" },
            summary.ToolNames.ToArray());
        Assert.AreEqual(
            """
            Tools: 2
            - deck.create_from_outline
            - pptx.export
            """.ReplaceLineEndings(),
            summary.ToSettingsText());
    }
}
