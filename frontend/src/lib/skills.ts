export const SKILL_LABEL: Record<string, string> = {
  pytorch: "PyTorch", "classical-ml": "Classical ML", rag: "RAG", "vector-db": "Vector DB",
  "llm-finetuning": "Fine-tuning", mlops: "MLOps", "llm-evals": "Evals",
};
export const skillLabel = (slug: string) => SKILL_LABEL[slug] ?? slug;
