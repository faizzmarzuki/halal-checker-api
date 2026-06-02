from halal_scanner.auth.email import Emailer, EmailMessage


def test_send_appends_to_outbox():
    em = Emailer()
    em.send("a@b.com", "Hi", "Body")
    assert len(em.outbox) == 1
    msg = em.outbox[0]
    assert isinstance(msg, EmailMessage)
    assert msg.to == "a@b.com"
    assert msg.subject == "Hi"
    assert msg.body == "Body"


def test_injected_backend_receives_message():
    seen = []
    em = Emailer(backend=seen.append)
    em.send("x@y.com", "S", "B")
    assert len(seen) == 1
    assert seen[0].to == "x@y.com"


def test_backend_failure_does_not_raise():
    def boom(msg):
        raise RuntimeError("smtp down")

    em = Emailer(backend=boom)
    em.send("a@b.com", "S", "B")  # must not raise
    assert len(em.outbox) == 1
