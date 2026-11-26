from unittest.mock import Mock

import pytest
import requests

import main
import telegram_notifier as notifier


def successful_response():
    response = Mock()
    response.raise_for_status.return_value = None
    return response


@pytest.mark.parametrize(
    ("text", "expected_sizes"),
    [
        ("a" * 4000, [4000]),
        ("a" * 4001, [4000, 1]),
        ("строка\n" * 1000, [3997, 3003]),
    ],
)
def test_split_message_is_lossless_and_within_limit(text, expected_sizes):
    chunks = notifier.split_message(text)

    assert "".join(chunks) == text
    assert [len(chunk) for chunk in chunks] == expected_sizes
    assert all(len(chunk) <= notifier.MAX_MESSAGE_LENGTH for chunk in chunks)


def test_html_is_escaped_and_proxy_is_used_first(monkeypatch):
    post = Mock(return_value=successful_response())
    monkeypatch.setattr(notifier.requests, "post", post)

    assert notifier.send_telegram("A < B & C > D", retries=1, delay=0) is True

    payload = post.call_args.kwargs["json"]
    assert payload["text"] == "A &lt; B &amp; C &gt; D"
    assert post.call_args.kwargs["proxies"] == notifier.PROXIES


def test_direct_connection_is_fallback_after_proxy_failure(monkeypatch):
    post = Mock(side_effect=[requests.ConnectionError("proxy down"), successful_response()])
    monkeypatch.setattr(notifier.requests, "post", post)

    assert notifier.send_telegram("test", retries=1, delay=0) is True

    assert post.call_args_list[0].kwargs["proxies"] == notifier.PROXIES
    assert "proxies" not in post.call_args_list[1].kwargs


def test_http_400_is_not_retried(monkeypatch):
    response = requests.Response()
    response.status_code = 400
    error = requests.HTTPError("Bad Request", response=response)
    post = Mock(side_effect=error)
    monkeypatch.setattr(notifier.requests, "post", post)

    assert notifier.send_telegram("bad", retries=3, delay=0) is None
    assert post.call_count == 1


def test_chunks_are_sent_in_order(monkeypatch):
    post = Mock(return_value=successful_response())
    monkeypatch.setattr(notifier.requests, "post", post)
    text = "a" * 8001

    assert notifier.send_telegram(text, retries=1, delay=0) is True

    assert [len(call.kwargs["json"]["text"]) for call in post.call_args_list] == [
        4000,
        4000,
        1,
    ]


def test_detailed_result_contains_only_unsent_and_later_parts(monkeypatch):
    post = Mock(
        side_effect=[
            successful_response(),
            requests.ConnectionError("proxy down"),
            requests.ConnectionError("direct down"),
        ]
    )
    monkeypatch.setattr(notifier.requests, "post", post)

    result = notifier.send_telegram_detailed("a" * 8001, retries=1, delay=0)

    assert result.status is False
    assert [len(part) for part in result.remaining_parts] == [4000, 1]


def test_send_or_queue_saves_only_unsent_parts(monkeypatch):
    result = notifier.TelegramSendResult(False, ("b" * 4000, "c"))
    save = Mock()
    success = notifier.TelegramSendResult(True, ())
    send = Mock(side_effect=[success, result, success])
    monkeypatch.setattr(main, "CHAT_IDS", ("test-chat", "extra-1", "extra-2"))
    monkeypatch.setattr(main, "send_telegram_detailed", send)
    monkeypatch.setattr(main, "load_failed_messages", Mock(return_value=["existing"]))
    monkeypatch.setattr(main, "save_failed_messages", save)

    assert main.send_or_queue("original") is False
    assert [call.kwargs["chat_id"] for call in send.call_args_list] == [
        "test-chat", "extra-1", "extra-2",
    ]
    save.assert_called_once_with([
        "existing",
        {"chat_id": "extra-1", "text": "b" * 3800},
        {"chat_id": "extra-1", "text": "b" * 200},
        {"chat_id": "extra-1", "text": "c"},
    ])


def test_legacy_long_queue_is_split_before_retry(monkeypatch):
    save = Mock()
    send = Mock(return_value=False)
    monkeypatch.setattr(main, "load_failed_messages", Mock(return_value=["x" * 8001]))
    monkeypatch.setattr(main, "save_failed_messages", save)
    monkeypatch.setattr(main, "send_telegram", send)

    main.retry_failed_messages()

    queued_again = save.call_args.args[0]
    assert [len(entry["text"]) for entry in queued_again] == [3800, 3800, 401]
    assert [call.kwargs["chat_id"] for call in send.call_args_list] == ["test-chat"] * 3


@pytest.mark.parametrize(
    ("send_result", "expected_queue"),
    [
        (False, [{"chat_id": "extra-1", "text": "queued message"}]),
        (None, []),
        (True, []),
    ],
)
def test_retry_queue_keeps_only_temporary_failures(
    monkeypatch, send_result, expected_queue
):
    save = Mock()
    entry = {"chat_id": "extra-1", "text": "queued message"}
    monkeypatch.setattr(main, "CHAT_IDS", ("test-chat", "extra-1"))
    monkeypatch.setattr(main, "load_failed_messages", Mock(return_value=[entry]))
    monkeypatch.setattr(main, "save_failed_messages", save)
    monkeypatch.setattr(main, "send_telegram", Mock(return_value=send_result))

    main.retry_failed_messages()

    save.assert_called_once_with(expected_queue)
    assert main.send_telegram.call_args.kwargs["chat_id"] == "extra-1"

