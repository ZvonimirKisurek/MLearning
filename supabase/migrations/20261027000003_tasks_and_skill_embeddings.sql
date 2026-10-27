-- Phase 2: per-task completion tracking, fractional skill levels, skill embeddings for retrieval.
set search_path = public, extensions;

-- Levels become fractional: one completed reading is worth ~0.15 points, which an int column would round to 0.
alter table public.skills        alter column level  type real, alter column target type real;
alter table public.skill_history alter column level  type real;

-- A skill is described in prose; that text is embedded once and used as a *query vector* to retrieve
-- the articles most relevant to the skill (the "R" in RAG).
alter table public.skills add column description text not null default '';
alter table public.skills add column embedding vector(1536);

update public.skills set description = case slug
  when 'pytorch' then 'PyTorch deep learning framework: tensors, autograd, nn.Module, training loops, DataLoader, GPU and CUDA, mixed precision, torch.compile, checkpointing, distributed training, debugging model training'
  when 'classical-ml' then 'Classical machine learning and the math behind it: linear and logistic regression, gradient descent, bias-variance, regularization, decision trees, gradient boosting, SVM, PCA, probability, linear algebra, cross-validation, feature engineering'
  when 'rag' then 'Retrieval-augmented generation: chunking strategies, embedding models, hybrid search, reranking, query rewriting, context assembly, citations, grounding, RAG evaluation, agentic retrieval'
  when 'vector-db' then 'Vector databases and similarity search: pgvector, HNSW and IVF indexes, approximate nearest neighbour, Qdrant, Weaviate, Pinecone, Milvus, embedding dimensionality, cosine similarity, filtered search, index tuning'
  when 'llm-finetuning' then 'Fine-tuning large language models: LoRA, QLoRA, PEFT, supervised fine-tuning, instruction tuning, RLHF, DPO, dataset curation, quantization, Hugging Face Transformers, TRL, evaluation of fine-tuned models'
  when 'mlops' then 'MLOps and model deployment: model serving, vLLM, Triton, ONNX, Docker and Kubernetes for ML, experiment tracking, MLflow, Weights and Biases, CI/CD for models, monitoring, drift detection, feature stores, on-device inference'
  when 'llm-evals' then 'LLM evaluation: benchmark design, LLM-as-judge, eval datasets, regression testing prompts, hallucination measurement, RAG evals, human evaluation, red teaming, observability and tracing of LLM apps'
  else description end
where description = '';

-- ---------------------------------------------------------------------------
-- daily_tasks: the 3 checkable items of a briefing. Completing one is what moves the skill matrix.
-- ---------------------------------------------------------------------------
create table public.daily_tasks (
  id             uuid primary key default gen_random_uuid(),
  briefing_id    uuid not null references public.daily_briefings(id) on delete cascade,
  kind           text not null check (kind in ('reading','hands_on','insight')),
  skill_slug     text not null references public.skills(slug),
  difficulty     int  not null default 1 check (difficulty between 1 and 3),
  title          text not null,
  completed_at   timestamptz,
  points_awarded real,
  unique (briefing_id, kind)
);
create index daily_tasks_briefing_idx on public.daily_tasks (briefing_id);
alter table public.daily_tasks enable row level security;

alter table public.skill_history add column task_id uuid references public.daily_tasks(id) on delete set null;
alter table public.skill_history add column delta real;
