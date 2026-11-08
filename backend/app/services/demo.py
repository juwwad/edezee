"""Zero-config demo provider.

A reviewer who clones the repository should be able to press "Generate" and see
the whole product — SSE progress, the slide review panel, the ``.pptx`` download
-- without signing up for an API key. ``DEMO_MODE=true`` swaps the real provider
for this deterministic scripted one.

This is a reliability aid for demos, not a product feature. It is off by
default, it never runs unless the operator asks for it, and every run it serves
carries an explicit warning so nobody mistakes the sample text for model output.
The real pipeline, parser, validator, and PPTX writer are unchanged.

Content comes from a small curated library covering the topics people actually
demo (the bundled sample syllabus, plus common AI and web-development courses).
Matching is on keywords, so a known topic yields a real deck and an unknown one
yields a topic-anchored fallback. Output is a pure function of ``(topic, depth)``:
the same input always produces the same deck, so a recorded demo replays exactly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from app.config import Settings

# The in-depth system prompt contains this phrase; the high-level one does not.
# Matching on it is how the scripted provider honours the depth toggle.
_IN_DEPTH_MARKER = "in-depth technical"

_TOPIC_PREFIX = "Topic:"


@dataclass(frozen=True)
class _Slide:
    bullets: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class _Entry:
    keywords: tuple[str, ...]
    high_level: _Slide
    in_depth: _Slide


# Ordered most-specific first: the first entry whose keyword appears in the
# topic wins, so "vector database" reaches the embedding entry before a broader
# one can claim it.
_LIBRARY: tuple[_Entry, ...] = (
    _Entry(
        keywords=("retrieval-augmented", "retrieval augmented", "rag"),
        high_level=_Slide(
            bullets=(
                "RAG lets a language model answer from documents it was never trained on, by finding the relevant passages first.",
                "The pipeline has two stages: a retriever that selects passages, and a generator that writes the answer from them.",
                "Because the answer is grounded in retrieved text, it can cite its sources and stay current without retraining.",
            ),
            notes=(
                "Open by contrasting this with asking a model to answer from memory: what happens when the topic is recent, "
                "private, or niche? Use that gap to motivate retrieval, then sketch the two stages before walking one question "
                "through both."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "A RAG pipeline embeds the query, retrieves the top-k passages by vector similarity, and conditions the generator on them.",
                "Retrieval quality bounds answer quality: if the relevant passage is never retrieved, no prompt can recover it.",
                "Chunk size, embedding model, and top-k are the three knobs that move end-to-end accuracy the most.",
                "Grounding cuts hallucination but does not remove it; the model can still overstate what a source says.",
            ),
            notes=(
                "Start from the failure mode: a purely parametric model cannot cite and cannot know anything after its training "
                "cut-off. Trace one query through embed, search, rank, and generate, naming the latency and cost at each hop. "
                "Close on evaluation, because retrieval recall and answer faithfulness fail for different reasons and need "
                "different fixes."
            ),
        ),
    ),
    _Entry(
        keywords=("embedding", "similarity search", "nearest neighbour", "vector database", "vector store"),
        high_level=_Slide(
            bullets=(
                "An embedding turns text into a list of numbers, arranged so that similar meanings sit close together.",
                "Similarity search ranks stored vectors by distance and returns the closest matches to a query.",
                "This is what lets search find a paraphrase rather than only an exact word match.",
            ),
            notes=(
                "Anchor the idea with a picture: words as points in space, meaning as distance. Ask learners to predict where "
                "'puppy' lands relative to 'dog' and to 'car', then reveal that the geometry, not a dictionary, drives retrieval."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "An embedding maps text to a dense vector in a learned space where cosine distance approximates semantic similarity.",
                "Exact nearest-neighbour search is linear in the corpus; approximate indexes such as HNSW trade a little recall for millisecond lookups.",
                "Cosine similarity suits cases where magnitude is irrelevant, dot product where the model was trained with it.",
                "Embedding models have a token limit, so text is chunked before encoding and the boundaries affect what is retrievable.",
            ),
            notes=(
                "Frame embeddings as a learned coordinate system rather than a hash. Then separate the two decisions learners "
                "usually conflate: how text is represented, and how the nearest neighbours are found. The second is where the "
                "accuracy-versus-latency trade-off lives."
            ),
        ),
    ),
    _Entry(
        keywords=("chunk",),
        high_level=_Slide(
            bullets=(
                "Chunking splits long documents into passages small enough to fit the context window and precise enough to be useful.",
                "Fixed-size splitting is simple but can cut a sentence in half; splitting on paragraphs and headings respects meaning.",
                "A small overlap between neighbouring chunks keeps context that would otherwise be lost at a boundary.",
            ),
            notes=(
                "Ask what goes wrong if a whole chapter is one chunk, then what goes wrong if every sentence is its own chunk. "
                "The exercise shows that chunking is a trade-off between fitting the window and keeping each passage coherent."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "Chunk boundaries set the ceiling on retrieval precision: a passage split mid-argument can be retrieved without its conclusion.",
                "Recursive splitting on structure — sections, then paragraphs, then sentences — preserves hierarchy better than a fixed window.",
                "Overlap is a cheap hedge against boundary loss, but it inflates the index and can surface the same text twice.",
                "Chunk size interacts with the embedding model's token limit and with how much context the generator can accept.",
            ),
            notes=(
                "Treat chunking as an indexing decision with measurable consequences. Have learners compare retrieval on the same "
                "document split two ways, and inspect which passages a query pulls back. The winning strategy is usually driven by "
                "document structure, not a single best-practice number."
            ),
        ),
    ),
    _Entry(
        keywords=("faithful", "hallucinat", "evaluat", "groundedness", "grounding"),
        high_level=_Slide(
            bullets=(
                "Faithfulness asks whether every claim in an answer is supported by the sources, not merely whether it sounds right.",
                "One practical method breaks the answer into claims and checks each claim against the retrieved passages.",
                "Scoring faithfulness apart from relevance shows whether a bad answer came from retrieval or from generation.",
            ),
            notes=(
                "Give learners two answers to the same question, one fluent but unsupported and one plain but sourced, and ask "
                "which they would trust. That contrast makes the point that fluency is not evidence."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "Faithfulness is measured per claim: decompose the answer, then verify each claim entails from the cited passages.",
                "It is deliberately separate from answer relevance and from retrieval recall, because each failure has a different fix.",
                "A model grading its own output is the weakest judge; independent checks or human spot-audits are needed to calibrate it.",
                "Report faithfulness with the retrieval configuration attached, since a score is meaningless without the passages it saw.",
            ),
            notes=(
                "Warn that a single aggregate score hides which stage failed. Walk through one answer where retrieval was correct "
                "but generation drifted, and one where generation was faithful to a passage that was itself off-topic. Then show "
                "why the two need separate metrics and separate remediations."
            ),
        ),
    ),
    _Entry(
        keywords=("prompt engineering", "prompting", "prompt"),
        high_level=_Slide(
            bullets=(
                "A prompt is a specification: it states the task, the audience, the format, and what counts as a good answer.",
                "Being explicit about the output shape is what makes results repeatable instead of lucky.",
                "Examples in the prompt show the format faster than describing it in prose.",
            ),
            notes=(
                "Have learners rewrite a vague request into a precise one and compare the outputs. The lesson is that most prompt "
                "problems are under-specified requirements, not model limitations."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "Prompt structure separates durable instructions from per-request data, which keeps behaviour stable as inputs vary.",
                "A strict output contract — a named schema, no prose around it — moves validation from guesswork to parsing.",
                "Few-shot examples raise consistency but consume context; they earn their place when the format is hard to describe.",
                "Prompts are code: they need version control, a regression set, and a change process.",
            ),
            notes=(
                "Reframe prompting as interface design rather than incantation. Show a prompt that returns prose, then the same "
                "prompt constrained to JSON, and let learners see that the second is testable. End on treating prompts as versioned "
                "artefacts with tests."
            ),
        ),
    ),
    _Entry(
        keywords=("fine-tun", "finetun", "lora", "rlhf"),
        high_level=_Slide(
            bullets=(
                "Fine-tuning continues training a model on your own examples to change its behaviour, not just its instructions.",
                "It suits style, format, and domain vocabulary better than it suits adding fresh facts.",
                "Retrieval is usually the cheaper fix when the problem is missing knowledge.",
            ),
            notes=(
                "Ask whether the problem is what the model knows or how it behaves. Knowledge points to retrieval; behaviour and "
                "format point to fine-tuning. That single question prevents most misapplied training runs."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "Parameter-efficient methods such as LoRA train small adapter matrices, cutting cost while leaving base weights frozen.",
                "Data quality dominates: a few hundred consistent, well-labelled examples beat thousands of noisy ones.",
                "Fine-tuning cannot reliably inject facts; it shifts distributions of style, tone, and output structure.",
                "Every fine-tune needs a held-out set, because overfitting to the training examples looks like success.",
            ),
            notes=(
                "Contrast teaching a model a manner with teaching it a fact. Then introduce LoRA as the practical default and "
                "spend the remaining time on dataset construction, since that is where most projects succeed or fail."
            ),
        ),
    ),
    _Entry(
        keywords=("transformer", "attention"),
        high_level=_Slide(
            bullets=(
                "A transformer reads a sequence all at once and weighs how much each word matters to every other word.",
                "That weighing is attention: a learned score for how relevant one position is to another.",
                "Reading in parallel, rather than one word at a time, is what made these models trainable at scale.",
            ),
            notes=(
                "Use a pronoun-resolution example to make attention concrete: to interpret 'it', the model must decide which earlier "
                "noun it refers to. Attention is the mechanism that assigns those weights."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "Self-attention computes queries, keys, and values per position, then weights values by the softmax of query-key similarity.",
                "Multi-head attention runs several of these projections in parallel, letting the model track different relationships at once.",
                "Positional encodings supply the order information that parallel attention would otherwise discard.",
                "Cost grows with the square of sequence length, which is why long-context work focuses on attention efficiency.",
            ),
            notes=(
                "Derive attention as a weighted average of value vectors, with the weights coming from a similarity score. Then "
                "show why multiple heads help, and finish on the quadratic cost that motivates the current efficiency research."
            ),
        ),
    ),
    _Entry(
        keywords=("next.js", "nextjs"),
        high_level=_Slide(
            bullets=(
                "Next.js is a React framework that adds routing, rendering choices, and a build step around plain React.",
                "Pages live in the file system, so a folder becomes a route without a separate routing configuration.",
                "It can render on the server, in the browser, or ahead of time, per route.",
            ),
            notes=(
                "Start from plain React and the pieces a team keeps rebuilding — routing, data loading, bundling — then show "
                "Next.js supplying them. The framing is convention over configuration."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "The App Router makes routing folder-based, with layouts that persist across navigations and nested segments.",
                "Rendering strategy is chosen per component: server by default, client only where interactivity or browser APIs are needed.",
                "Server components cut the JavaScript shipped to the browser, which is the main performance lever.",
                "Data fetching and caching are explicit parts of the framework's contract rather than ad-hoc effects.",
            ),
            notes=(
                "Frame the App Router as a rendering-boundary decision. Show the same page as a server component and as a client "
                "component, and compare the bundle. The rule of thumb: push interactivity to the leaves."
            ),
        ),
    ),
    _Entry(
        keywords=("server component", "client component"),
        high_level=_Slide(
            bullets=(
                "A server component runs on the server and sends finished markup, so its code never reaches the browser.",
                "A client component runs in the browser and is what handles clicks, state, and browser-only APIs.",
                "The usual pattern is server components by default, with client components only where interactivity is needed.",
            ),
            notes=(
                "Ask which parts of a page actually need the browser: a button does, a heading does not. That question sorts a page "
                "into the two kinds of component better than any rule."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "Server components can read databases and secrets directly, since their code is never shipped to the client.",
                "Client components are the boundary where interactivity and hooks such as state and effects are allowed.",
                "Passing data across the boundary requires serialisable props; functions and class instances cannot cross.",
                "Pushing interactivity to the leaves keeps most of the tree on the server and minimises the client bundle.",
            ),
            notes=(
                "Emphasise the serialisation boundary as the thing that trips people up. Walk through a component tree and mark "
                "where the boundary sits, then show how moving it changes the shipped bundle."
            ),
        ),
    ),
    _Entry(
        keywords=("data fetching", "fetch", "caching", "cache"),
        high_level=_Slide(
            bullets=(
                "Data fetching is the decision of when and where a page gets its data: on the server, in the browser, or ahead of time.",
                "Fetching on the server avoids a loading spinner and keeps API credentials out of the browser.",
                "Caching decides how often that data is refreshed versus served from a stored copy.",
            ),
            notes=(
                "Have learners trace one page load and mark each moment data is requested. Most performance complaints are answered "
                "by moving a request earlier or caching a result."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "Where the fetch happens determines the caching layer: server fetches can be cached and revalidated at the framework level.",
                "Request waterfalls — a fetch that waits on another fetch — dominate latency, so they are the first thing to flatten.",
                "Stale-while-revalidate serves a cached response immediately and refreshes it in the background.",
                "Cache invalidation is the hard part; choosing a revalidation window is a product decision, not just a technical one.",
            ),
            notes=(
                "Trace a waterfall and count the round trips, then flatten it and count again. The lesson is that the number of "
                "sequential hops matters more than the speed of any single request."
            ),
        ),
    ),
    _Entry(
        keywords=("data structure", "hash map", "linked list", "binary tree", "array", "queue"),
        high_level=_Slide(
            bullets=(
                "A data structure is a way of organising values so that the operations you need are fast.",
                "The choice is driven by which operations dominate: lookup, insertion, deletion, or ordered traversal.",
                "Arrays give fast indexed access; hash maps give fast lookup by key; trees keep data ordered.",
            ),
            notes=(
                "Have learners pick a structure for a concrete task — a phone book, an undo history, a priority queue — and justify "
                "it by the operations they need. The structure follows from the access pattern."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "Hash maps give expected constant-time lookup, at the cost of no ordering and sensitivity to hash quality.",
                "Balanced trees keep operations logarithmic and preserve order, which matters for range queries.",
                "Linked lists trade indexed access for constant-time insertion once the position is known.",
                "Amortised analysis explains why a dynamic array's occasional resize is still cheap on average.",
            ),
            notes=(
                "Anchor each structure to a complexity table rather than a definition. Ask which operation must be fast, then "
                "eliminate structures that fail that requirement. Close on amortised cost, which is where intuition usually breaks."
            ),
        ),
    ),
    _Entry(
        keywords=("sql", "relational", "normalis", "normaliz", "database", "index"),
        high_level=_Slide(
            bullets=(
                "A relational database stores data in tables and answers questions by joining them.",
                "Normalisation removes duplicated facts so that updating one value does not require changing many rows.",
                "An index makes lookups fast at the cost of extra work on every write.",
            ),
            notes=(
                "Show a table with a repeated value and ask what happens when it changes. Duplication is the problem normalisation "
                "solves, and the question makes that concrete."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "Normal forms remove redundancy incrementally: first repeating groups, then partial and transitive dependencies.",
                "Indexes accelerate reads by trading write cost and storage, so indexing every column is a mistake.",
                "Query plans reveal whether the engine used an index or scanned the table, which is where tuning starts.",
                "Transactions provide atomicity and isolation, and the isolation level chosen governs which anomalies remain possible.",
            ),
            notes=(
                "Frame normalisation as protecting a single source of truth, then introduce denormalisation as a deliberate "
                "read-performance trade. Finish on reading a query plan, since that turns tuning from guesswork into evidence."
            ),
        ),
    ),
    _Entry(
        keywords=("http", "tcp", "network", "rest", "dns"),
        high_level=_Slide(
            bullets=(
                "HTTP is a request-and-response protocol: a client asks, a server answers, and the connection closes or is reused.",
                "Methods carry intent — GET reads, POST creates — and status codes report what happened.",
                "Layered beneath it, TCP guarantees that the bytes arrive complete and in order.",
            ),
            notes=(
                "Trace one page load from the browser to the server and back, naming each layer as you go. The goal is to show "
                "that 'the network' is several distinct steps, each with its own failure mode."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "HTTP is stateless, so state is carried by cookies, tokens, or headers rather than by the connection.",
                "Status codes divide into classes: 2xx success, 3xx redirection, 4xx client error, 5xx server error.",
                "TCP's handshake and retransmission give reliable ordered delivery on top of an unreliable network.",
                "Caching headers and conditional requests let a client avoid transferring what it already holds.",
            ),
            notes=(
                "Emphasise statelessness as the design decision that makes HTTP scalable, then show how headers restore the "
                "continuity applications need. Finish on caching, where correctness and performance are in tension."
            ),
        ),
    ),
    _Entry(
        keywords=("machine learning", "supervised", "regression", "classification", "overfit", "training"),
        high_level=_Slide(
            bullets=(
                "Machine learning fits a model to examples so it can make predictions on new ones it has not seen.",
                "Supervised learning trains on labelled pairs; unsupervised learning looks for structure without labels.",
                "The test is generalisation: how the model performs on data it was not trained on.",
            ),
            notes=(
                "Contrast memorising the training examples with learning the pattern. A model that aces the training set and fails "
                "the test set has memorised; that distinction motivates everything that follows."
            ),
        ),
        in_depth=_Slide(
            bullets=(
                "The bias-variance trade-off explains underfitting and overfitting as two directions of the same error.",
                "Held-out validation and cross-validation estimate generalisation, which training error cannot.",
                "Regularisation and early stopping constrain model complexity to reduce variance.",
                "Data leakage — information from the test set reaching training — inflates scores and is the most common silent failure.",
            ),
            notes=(
                "Start from training error being a misleading signal, then introduce validation as the honest estimate. Spend "
                "time on leakage, because it produces excellent numbers on a model that will fail in production."
            ),
        ),
    ),
)


def demo_content(topic: str, *, in_depth: bool = False) -> dict:
    """Sample slide content for ``topic``.

    Deterministic: the same topic and depth always yield the same deck, so a
    recorded demo replays exactly. Known topics come from the curated library;
    anything else gets a topic-anchored fallback so the deck never reads as
    blank filler.
    """
    title = _title(topic)
    entry = _match(title)
    slide = None
    if entry is not None:
        slide = entry.in_depth if in_depth else entry.high_level
    if slide is None:
        slide = _fallback(title, in_depth=in_depth)
    return {
        "slide_title": title[:120],
        "bullet_points": list(slide.bullets),
        "speaker_notes": slide.notes,
    }


def _title(topic: str) -> str:
    return topic.strip().rstrip("?.") or "Untitled topic"


def _match(title: str) -> _Entry | None:
    haystack = title.lower()
    for entry in _LIBRARY:
        if any(_keyword_hits(keyword, haystack) for keyword in entry.keywords):
            return entry
    return None


def _keyword_hits(keyword: str, haystack: str) -> bool:
    """True when ``keyword`` starts a word in ``haystack``.

    The keywords are stems ("chunk" matches "chunking"), so the match is
    anchored only at the start of a word. A bare substring test let the "rag"
    keyword fire inside "storage", "average", and "paragraph", serving the
    retrieval-augmented-generation slide for a topic about neither.
    """
    return re.search(r"\b" + re.escape(keyword), haystack) is not None


def _fallback(title: str, *, in_depth: bool) -> _Slide:
    """Topic-anchored content for a topic the library does not cover.

    It names the topic so the deck is not obviously boilerplate, and it stays
    deliberately general: with no model call there is nothing to ground specific
    claims in, and inventing facts would be worse than being plain.
    """
    if in_depth:
        return _Slide(
            bullets=(
                f"{title} is best taught by working one concrete instance end to end before generalising.",
                "The mechanism has distinct stages; naming each stage is what lets a learner debug the whole.",
                "Common misconceptions cluster at the boundary between stages rather than inside any one of them.",
            ),
            notes=(
                f"Trace a single worked instance of {title} from start to finish, narrating each stage as you go. Then ask "
                "learners to identify where their own confusion sits, which usually reveals a boundary between stages rather "
                "than a missing fact."
            ),
        )
    return _Slide(
        bullets=(
            f"{title} is introduced here so that later topics can build on it.",
            "The key terms are defined first, then applied to one example the learner can picture.",
            "Learners should be able to explain the idea in their own words before moving on.",
        ),
        notes=(
            f"Begin by asking what the group already knows about {title}, and use their answers to find the right starting "
            "point. Introduce the vocabulary only once the underlying idea is clear, then work the example together."
        ),
    )


class DemoTransport(httpx.AsyncBaseTransport):
    """Answers every chat-completion request with demo content for the topic.

    It parses the topic and the requested depth out of the prompt so the deck
    matches what the user asked for, and it counts requests so the demo can be
    reproduced exactly.
    """

    def __init__(self) -> None:
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        body = json.loads(request.content.decode())
        messages = body.get("messages", [])
        topic = _topic_from_messages(messages)
        content = demo_content(topic, in_depth=_is_in_depth(messages))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": json.dumps(content)}}]},
            request=request,
        )


def _topic_from_messages(messages: list[dict]) -> str:
    for message in reversed(messages):
        content = message.get("content")
        if not isinstance(content, str):
            continue
        for line in content.splitlines():
            if line.startswith(_TOPIC_PREFIX):
                return line.removeprefix(_TOPIC_PREFIX).strip()
    return "Untitled topic"


def _is_in_depth(messages: list[dict]) -> bool:
    for message in messages:
        content = message.get("content")
        if isinstance(content, str) and _IN_DEPTH_MARKER in content:
            return True
    return False


def build_demo_llm(settings: Settings):
    """An :class:`LLMService` wired to the scripted provider.

    Imported lazily to avoid a circular import: ``llm`` does not import ``demo``.
    """
    from app.services.llm import LLMService

    client = httpx.AsyncClient(transport=DemoTransport(), timeout=settings.llm_timeout_seconds)
    return LLMService(settings, client=client)
