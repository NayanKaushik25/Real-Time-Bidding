const e = React.createElement;
const { useEffect, useMemo, useState } = React;

function formatCurrency(amount) {
  return `Rs.${Number(amount || 0).toLocaleString("en-IN")}`;
}

function formatTime(seconds) {
  const total = Math.max(0, Number(seconds || 0));
  const mins = String(Math.floor(total / 60)).padStart(2, "0");
  const secs = String(total % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

function App() {
  const [state, setState] = useState(null);
  const [name, setName] = useState("");
  const [bid, setBid] = useState("");
  const [status, setStatus] = useState("Connecting to auction server...");
  const [submitting, setSubmitting] = useState(false);

  async function loadState() {
    try {
      const response = await fetch("/api/state");
      const data = await response.json();
      setState(data);
      if (!data.auctionActive && data.highestBidder) {
        setStatus(`Auction closed. Winner: ${data.highestBidder}`);
      } else if (!data.auctionActive) {
        setStatus("Auction closed with no valid bids.");
      } else {
        setStatus("Auction is live. Place a higher bid to reset the timer.");
      }
    } catch (error) {
      setStatus("Unable to reach the auction server.");
    }
  }

  useEffect(() => {
    loadState();
    const timer = window.setInterval(loadState, 1000);
    return () => window.clearInterval(timer);
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!name.trim() || !bid.trim()) {
      setStatus("Enter both your name and a bid amount.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch("/api/bid", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: name.trim(),
          bid: Number(bid),
        }),
      });

      const result = await response.json();
      setStatus(result.message);
      if (result.state) {
        setState(result.state);
      }
      if (result.ok) {
        setBid("");
      }
    } catch (error) {
      setStatus("Bid submission failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const leaderLabel = useMemo(() => {
    if (!state || !state.highestBidder) {
      return "No bids yet";
    }
    return `${state.highestBidder} is leading`;
  }, [state]);

  if (!state) {
    return e(
      "main",
      { className: "app-shell" },
      e("section", { className: "hero loading-card" }, e("p", null, status))
    );
  }

  return e(
    "main",
    { className: "app-shell" },
    e(
      "section",
      { className: "hero" },
      e("div", { className: "hero-copy" }, [
        e("p", { className: "eyebrow", key: "eyebrow" }, "Live auction dashboard"),
        e("h1", { key: "title" }, state.itemName || "Auction item"),
        e(
          "p",
          { className: "hero-text", key: "text" },
          "Track the countdown, watch the current leader, and place bids from your browser."
        ),
      ]),
      e(
        "div",
        { className: "hero-stats" },
        [
          e(
            "article",
            { className: "stat-card primary", key: "highest" },
            [
              e("span", { className: "stat-label", key: "label" }, "Highest bid"),
              e("strong", { className: "stat-value", key: "value" }, formatCurrency(state.highestBid)),
              e("p", { className: "stat-meta", key: "meta" }, leaderLabel),
            ]
          ),
          e(
            "article",
            { className: "stat-card", key: "timer" },
            [
              e("span", { className: "stat-label", key: "label" }, "Time left"),
              e("strong", { className: "stat-value", key: "value" }, formatTime(state.remainingTime)),
              e(
                "p",
                { className: "stat-meta", key: "meta" },
                state.auctionActive ? "Each winning bid resets the clock." : "Bidding is closed."
              ),
            ]
          ),
          e(
            "article",
            { className: "stat-card", key: "base" },
            [
              e("span", { className: "stat-label", key: "label" }, "Base price"),
              e("strong", { className: "stat-value", key: "value" }, formatCurrency(state.basePrice)),
              e("p", { className: "stat-meta", key: "meta" }, `Window: ${state.auctionDuration} seconds`),
            ]
          ),
        ]
      )
    ),
    e(
      "section",
      { className: "content-grid" },
      e(
        "article",
        { className: "panel panel-form" },
        [
          e("h2", { key: "title" }, "Place your bid"),
          e("p", { className: "panel-copy", key: "copy" }, status),
          e(
            "form",
            { className: "bid-form", onSubmit: handleSubmit, key: "form" },
            [
              e("label", { className: "field-label", htmlFor: "name", key: "name-label" }, "Your name"),
              e("input", {
                id: "name",
                className: "field-input",
                type: "text",
                value: name,
                onChange: (event) => setName(event.target.value),
                placeholder: "Aarav",
                key: "name",
              }),
              e("label", { className: "field-label", htmlFor: "bid", key: "bid-label" }, "Bid amount"),
              e("input", {
                id: "bid",
                className: "field-input",
                type: "number",
                min: "0",
                step: "1",
                value: bid,
                onChange: (event) => setBid(event.target.value),
                placeholder: "2500",
                key: "bid",
              }),
              e(
                "button",
                {
                  className: "submit-button",
                  type: "submit",
                  disabled: submitting || !state.auctionActive,
                  key: "button",
                },
                submitting ? "Submitting..." : state.auctionActive ? "Submit bid" : "Auction closed"
              ),
            ]
          ),
        ]
      ),
      e(
        "article",
        { className: "panel panel-feed" },
        [
          e("h2", { key: "title" }, "Auction feed"),
          e(
            "div",
            { className: "event-list", key: "events" },
            (state.events || []).length
              ? state.events
                  .slice()
                  .reverse()
                  .map((entry, index) =>
                    e(
                      "div",
                      { className: "event-item", key: `${entry.time}-${index}` },
                      [
                        e("span", { className: "event-time", key: "time" }, entry.time),
                        e("p", { className: "event-message", key: "message" }, entry.message),
                      ]
                    )
                  )
              : [e("p", { className: "event-empty", key: "empty" }, "No auction events yet.")]
          ),
        ]
      )
    )
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(e(App));
