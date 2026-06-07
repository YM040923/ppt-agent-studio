using System;
using System.Buffers;
using System.Collections.Generic;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;

namespace PptAgentStudio_App.Services;

public sealed record AgentRuntimeEvent(
    int Seq,
    string Type,
    string SessionId,
    string? DeckId,
    int? DeckRevision,
    JsonElement Payload);

public sealed class AgentSessionClient
{
    private readonly Uri _endpoint;
    private readonly AgentWorkspaceIdentity _identity;

    public AgentSessionClient(
        string endpoint = "ws://127.0.0.1:8765",
        string sessionId = "desktop-session",
        string deckId = "desktop-deck")
    {
        _endpoint = new Uri(endpoint);
        _identity = new AgentWorkspaceIdentity(sessionId, deckId);
    }

    public async Task StartNewDeckAsync(CancellationToken cancellationToken = default)
    {
        using var resetCancellation = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        resetCancellation.CancelAfter(TimeSpan.FromSeconds(1));

        try
        {
            await ResetCurrentDeckAsync(resetCancellation.Token);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception)
        {
        }

        _identity.StartNewDeck();
    }

    public async IAsyncEnumerable<AgentRuntimeEvent> SendUserMessageAsync(
        string text,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        using var socket = new ClientWebSocket();
        await socket.ConnectAsync(_endpoint, cancellationToken);

        var request = JsonSerializer.Serialize(new
        {
            type = "user.message",
            session_id = _identity.SessionId,
            deck_id = _identity.DeckId,
            payload = new { text }
        });
        await socket.SendAsync(
            Encoding.UTF8.GetBytes(request),
            WebSocketMessageType.Text,
            true,
            cancellationToken);

        while (socket.State == WebSocketState.Open)
        {
            var message = await ReceiveTextAsync(socket, cancellationToken);
            if (string.IsNullOrWhiteSpace(message))
            {
                yield break;
            }

            var runtimeEvent = ParseEvent(message);
            yield return runtimeEvent;

            if (AgentTurnCompletionPolicy.ShouldEndTurn(runtimeEvent.Type, runtimeEvent.Payload))
            {
                await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "turn complete", cancellationToken);
                yield break;
            }
        }
    }

    public async Task<RuntimeConfigSummary> GetRuntimeConfigAsync(CancellationToken cancellationToken = default)
    {
        using var socket = new ClientWebSocket();
        await socket.ConnectAsync(_endpoint, cancellationToken);

        var request = JsonSerializer.Serialize(new
        {
            type = "runtime.config",
            session_id = _identity.SessionId
        });
        await socket.SendAsync(
            Encoding.UTF8.GetBytes(request),
            WebSocketMessageType.Text,
            true,
            cancellationToken);

        var message = await ReceiveTextAsync(socket, cancellationToken);
        var runtimeEvent = ParseEvent(message);
        await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "config received", cancellationToken);
        return RuntimeConfigSummary.FromPayload(runtimeEvent.Payload);
    }

    private async Task ResetCurrentDeckAsync(CancellationToken cancellationToken)
    {
        using var socket = new ClientWebSocket();
        await socket.ConnectAsync(_endpoint, cancellationToken);

        var request = JsonSerializer.Serialize(new
        {
            type = "session.reset",
            session_id = _identity.SessionId,
            deck_id = _identity.DeckId
        });
        await socket.SendAsync(
            Encoding.UTF8.GetBytes(request),
            WebSocketMessageType.Text,
            true,
            cancellationToken);

        var message = await ReceiveTextAsync(socket, cancellationToken);
        if (!string.IsNullOrWhiteSpace(message))
        {
            _ = ParseEvent(message);
        }

        await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "session reset", cancellationToken);
    }

    private static AgentRuntimeEvent ParseEvent(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        return new AgentRuntimeEvent(
            Seq: root.GetProperty("seq").GetInt32(),
            Type: root.GetProperty("type").GetString() ?? "",
            SessionId: root.GetProperty("session_id").GetString() ?? "",
            DeckId: root.TryGetProperty("deck_id", out var deckId) ? deckId.GetString() : null,
            DeckRevision: root.TryGetProperty("deck_revision", out var revision) ? revision.GetInt32() : null,
            Payload: root.GetProperty("payload").Clone());
    }

    private static async Task<string> ReceiveTextAsync(ClientWebSocket socket, CancellationToken cancellationToken)
    {
        using var owner = MemoryPool<byte>.Shared.Rent(16 * 1024);
        var buffer = owner.Memory;
        var builder = new StringBuilder();

        while (true)
        {
            var result = await socket.ReceiveAsync(buffer, cancellationToken);
            if (result.MessageType == WebSocketMessageType.Close)
            {
                return "";
            }

            builder.Append(Encoding.UTF8.GetString(buffer.Span[..result.Count]));
            if (result.EndOfMessage)
            {
                return builder.ToString();
            }
        }
    }
}
