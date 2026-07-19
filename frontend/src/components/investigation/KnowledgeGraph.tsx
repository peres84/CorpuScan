import { useEffect, useState, useCallback } from "react";
import { Network, Circle, AlertCircle } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

interface GraphEntity {
  name: string;
  entity_type: string;
  source_doc_id: string;
}

interface GraphRelationship {
  source_entity: string;
  target_entity: string;
  shared_entity: string;
  entity_type: string;
}

interface GraphData {
  entities: GraphEntity[];
  relationships: GraphRelationship[];
}

interface KnowledgeGraphProps {
  jobId: string;
}

const TYPE_COLORS: Record<string, string> = {
  vendor: "bg-blue-500",
  person: "bg-red-500",
  account: "bg-green-500",
  amount: "bg-orange-500",
  date: "bg-purple-500",
  invoice_number: "bg-cyan-500",
};

const TYPE_TEXT_COLORS: Record<string, string> = {
  vendor: "text-blue-600",
  person: "text-red-600",
  account: "text-green-600",
  amount: "text-orange-600",
  date: "text-purple-600",
  invoice_number: "text-cyan-600",
};

const KnowledgeGraph = ({ jobId }: KnowledgeGraphProps) => {
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<GraphEntity | null>(null);
  const [relatedEntities, setRelatedEntities] = useState<
    { name: string; entity_type: string; documents: string[] }[]
  >([]);

  const fetchGraph = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/investigations/${jobId}/graph`);
      if (response.ok) {
        setGraph(await response.json());
      } else if (response.status === 404) {
        setError("Knowledge graph not available");
      }
    } catch {
      setError("Failed to load knowledge graph");
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const handleEntityClick = async (entity: GraphEntity) => {
    setSelectedEntity(entity);
    try {
      const response = await fetch(
        `${API_BASE}/investigations/${jobId}/related?entity=${encodeURIComponent(entity.name)}`
      );
      if (response.ok) {
        setRelatedEntities(await response.json());
      }
    } catch {
      setRelatedEntities([]);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-6 text-muted-foreground">
        <Network className="h-5 w-5 animate-pulse" />
        <span>Loading knowledge graph...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 p-6 text-muted-foreground">
        <AlertCircle className="h-5 w-5" />
        <span>{error}</span>
      </div>
    );
  }

  if (!graph || graph.entities.length === 0) {
    return (
      <div className="flex items-center gap-2 p-6 text-muted-foreground">
        <Network className="h-5 w-5" />
        <span>Knowledge graph not available. Enable Cognee for relationship discovery.</span>
      </div>
    );
  }

  // Group entities by type
  const entityByType: Record<string, GraphEntity[]> = {};
  for (const entity of graph.entities) {
    const type = entity.entity_type || "unknown";
    if (!entityByType[type]) entityByType[type] = [];
    entityByType[type].push(entity);
  }

  return (
    <div className="space-y-4">
      {/* Legend */}
      <div className="flex flex-wrap gap-3">
        {Object.entries(entityByType).map(([type, entities]) => (
          <div key={type} className="flex items-center gap-1.5 text-xs">
            <div className={`w-2.5 h-2.5 rounded-full ${TYPE_COLORS[type] || "bg-gray-400"}`} />
            <span className="text-muted-foreground capitalize">
              {type} ({entities.length})
            </span>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Entity list by type */}
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {Object.entries(entityByType).map(([type, entities]) => (
            <div key={type}>
              <h4 className={`text-xs font-semibold uppercase mb-1 ${TYPE_TEXT_COLORS[type] || "text-muted-foreground"}`}>
                {type}
              </h4>
              <div className="flex flex-wrap gap-1">
                {entities.slice(0, 20).map((entity) => (
                  <button
                    key={`${entity.name}-${entity.source_doc_id}`}
                    onClick={() => handleEntityClick(entity)}
                    className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                      selectedEntity?.name === entity.name
                        ? "border-primary bg-primary/10 text-foreground"
                        : "border-border text-muted-foreground hover:border-primary/50"
                    }`}
                  >
                    {entity.name}
                  </button>
                ))}
                {entities.length > 20 && (
                  <span className="px-2 py-0.5 text-xs text-muted-foreground">
                    +{entities.length - 20} more
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Selected entity detail panel */}
        <div className="rounded-lg border p-4 min-h-[200px]">
          {selectedEntity ? (
            <div className="space-y-3">
              <div>
                <h3 className="text-sm font-semibold text-foreground">{selectedEntity.name}</h3>
                <p className="text-xs text-muted-foreground capitalize">
                  Type: {selectedEntity.entity_type} | Source: {selectedEntity.source_doc_id}
                </p>
              </div>

              {relatedEntities.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-1">
                    Connected entities ({relatedEntities.length})
                  </h4>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {relatedEntities.map((rel) => (
                      <div
                        key={rel.name}
                        className="flex items-center gap-2 text-xs px-2 py-1 rounded bg-muted/50"
                      >
                        <Circle
                          className={`h-2 w-2 fill-current ${TYPE_TEXT_COLORS[rel.entity_type] || "text-gray-400"}`}
                        />
                        <span className="font-medium text-foreground">{rel.name}</span>
                        <span className="text-muted-foreground capitalize">({rel.entity_type})</span>
                        <span className="ml-auto text-muted-foreground">
                          {rel.documents.length} doc{rel.documents.length !== 1 ? "s" : ""}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {relatedEntities.length === 0 && (
                <p className="text-xs text-muted-foreground">No connected entities found.</p>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Click an entity to see connections
            </div>
          )}
        </div>
      </div>

      {/* Relationship summary */}
      {graph.relationships.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground mb-2">
            Relationships ({graph.relationships.length})
          </h4>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {graph.relationships.slice(0, 20).map((rel, idx) => (
              <div key={idx} className="text-xs text-muted-foreground px-2 py-1 rounded bg-muted/30">
                <span className="font-mono">{rel.shared_entity}</span>
                <span className="mx-1">connects</span>
                <span className="font-medium">{rel.source_entity.slice(0, 8)}</span>
                <span className="mx-1">↔</span>
                <span className="font-medium">{rel.target_entity.slice(0, 8)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default KnowledgeGraph;
