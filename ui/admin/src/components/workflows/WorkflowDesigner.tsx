import React, { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';

// Types
interface WorkflowNode {
  id: string;
  type: 'start' | 'end' | 'llm' | 'tool' | 'condition' | 'parallel' | 'human';
  label: string;
  config: Record<string, any>;
  position: { x: number; y: number };
}

interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  condition?: string;
}

interface Workflow {
  id: string;
  name: string;
  description: string;
  templateType: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  inputSchema: Record<string, any>;
  isActive: boolean;
}

// Node type configurations
const NODE_TYPES = {
  start: { label: 'Start', color: 'bg-green-500', icon: '▶' },
  end: { label: 'End', color: 'bg-red-500', icon: '⏹' },
  llm: { label: 'LLM Call', color: 'bg-blue-500', icon: '🤖' },
  tool: { label: 'Tool/MCP', color: 'bg-purple-500', icon: '🔧' },
  condition: { label: 'Condition', color: 'bg-yellow-500', icon: '⚡' },
  parallel: { label: 'Parallel', color: 'bg-cyan-500', icon: '⫿' },
  human: { label: 'Human Input', color: 'bg-orange-500', icon: '👤' },
};

// Node Component
const WorkflowNodeComponent: React.FC<{
  node: WorkflowNode;
  isSelected: boolean;
  onSelect: () => void;
  onDragStart: (e: React.DragEvent) => void;
  onDrag: (e: React.DragEvent) => void;
  onDragEnd: (e: React.DragEvent) => void;
}> = ({ node, isSelected, onSelect, onDragStart, onDrag, onDragEnd }) => {
  const nodeType = NODE_TYPES[node.type];

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDrag={onDrag}
      onDragEnd={onDragEnd}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
      style={{
        position: 'absolute',
        left: node.position.x,
        top: node.position.y,
        transform: 'translate(-50%, -50%)',
      }}
      className={`
        cursor-move select-none
        ${isSelected ? 'ring-2 ring-blue-500 ring-offset-2' : ''}
      `}
    >
      <div className={`
        w-32 rounded-lg shadow-lg overflow-hidden
        ${isSelected ? 'shadow-blue-200' : ''}
      `}>
        <div className={`${nodeType.color} text-white px-3 py-1 text-center text-sm font-medium`}>
          <span className="mr-1">{nodeType.icon}</span>
          {nodeType.label}
        </div>
        <div className="bg-white px-3 py-2 text-center">
          <span className="text-sm text-gray-700">{node.label}</span>
        </div>
      </div>
      {/* Connection points */}
      <div className="absolute -top-1 left-1/2 transform -translate-x-1/2 w-3 h-3 bg-gray-400 rounded-full border-2 border-white" />
      <div className="absolute -bottom-1 left-1/2 transform -translate-x-1/2 w-3 h-3 bg-gray-400 rounded-full border-2 border-white" />
    </div>
  );
};

// Edge Component (SVG line)
const WorkflowEdgeComponent: React.FC<{
  edge: WorkflowEdge;
  sourceNode: WorkflowNode;
  targetNode: WorkflowNode;
  isSelected: boolean;
  onSelect: () => void;
}> = ({ edge, sourceNode, targetNode, isSelected, onSelect }) => {
  const startX = sourceNode.position.x;
  const startY = sourceNode.position.y + 30;
  const endX = targetNode.position.x;
  const endY = targetNode.position.y - 30;

  // Calculate control points for curved line
  const midY = (startY + endY) / 2;

  const path = `M ${startX} ${startY} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}`;

  return (
    <g onClick={onSelect} className="cursor-pointer">
      {/* Invisible wider path for easier clicking */}
      <path d={path} fill="none" stroke="transparent" strokeWidth={20} />
      {/* Visible path */}
      <path
        d={path}
        fill="none"
        stroke={isSelected ? '#3b82f6' : '#9ca3af'}
        strokeWidth={isSelected ? 3 : 2}
        markerEnd="url(#arrowhead)"
      />
      {/* Edge label */}
      {edge.label && (
        <text
          x={(startX + endX) / 2}
          y={(startY + endY) / 2 - 10}
          textAnchor="middle"
          className="text-xs fill-gray-500"
        >
          {edge.label}
        </text>
      )}
    </g>
  );
};

// Node Properties Panel
const NodePropertiesPanel: React.FC<{
  node: WorkflowNode;
  onChange: (node: WorkflowNode) => void;
  onDelete: () => void;
}> = ({ node, onChange, onDelete }) => {
  const nodeType = NODE_TYPES[node.type];

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold flex items-center gap-2">
          <span className={`${nodeType.color} text-white px-2 py-1 rounded text-sm`}>
            {nodeType.icon} {nodeType.label}
          </span>
        </h3>
        {node.type !== 'start' && node.type !== 'end' && (
          <button
            onClick={onDelete}
            className="text-red-500 hover:text-red-700"
          >
            Delete
          </button>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Label</label>
        <input
          type="text"
          value={node.label}
          onChange={(e) => onChange({ ...node, label: e.target.value })}
          className="w-full px-3 py-2 border rounded-md"
        />
      </div>

      {/* Type-specific configuration */}
      {node.type === 'llm' && (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
            <select
              value={node.config.model || 'gpt-4o-mini'}
              onChange={(e) => onChange({ ...node, config: { ...node.config, model: e.target.value } })}
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="gpt-4o-mini">GPT-4o Mini</option>
              <option value="gpt-4o">GPT-4o</option>
              <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
              <option value="claude-3-haiku">Claude 3 Haiku</option>
              <option value="llama-3.1-70b">Llama 3.1 70B</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">System Prompt</label>
            <textarea
              value={node.config.systemPrompt || ''}
              onChange={(e) => onChange({ ...node, config: { ...node.config, systemPrompt: e.target.value } })}
              rows={3}
              className="w-full px-3 py-2 border rounded-md"
              placeholder="You are a helpful assistant..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Temperature</label>
            <input
              type="range"
              min={0}
              max={100}
              value={(node.config.temperature || 0.7) * 100}
              onChange={(e) => onChange({ ...node, config: { ...node.config, temperature: parseInt(e.target.value) / 100 } })}
              className="w-full"
            />
            <span className="text-sm text-gray-500">{node.config.temperature || 0.7}</span>
          </div>
        </>
      )}

      {node.type === 'tool' && (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">MCP Server</label>
            <select
              value={node.config.mcpServer || ''}
              onChange={(e) => onChange({ ...node, config: { ...node.config, mcpServer: e.target.value } })}
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="">Select server...</option>
              <option value="filesystem">Filesystem</option>
              <option value="database">Database (PostgreSQL)</option>
              <option value="brave-search">Brave Search</option>
              <option value="github">GitHub</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tool Name</label>
            <input
              type="text"
              value={node.config.toolName || ''}
              onChange={(e) => onChange({ ...node, config: { ...node.config, toolName: e.target.value } })}
              className="w-full px-3 py-2 border rounded-md"
              placeholder="e.g., read_file, query_database"
            />
          </div>
        </>
      )}

      {node.type === 'condition' && (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Condition Expression</label>
            <textarea
              value={node.config.condition || ''}
              onChange={(e) => onChange({ ...node, config: { ...node.config, condition: e.target.value } })}
              rows={3}
              className="w-full px-3 py-2 border rounded-md font-mono text-sm"
              placeholder="state.result.status == 'success'"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">True Branch Label</label>
            <input
              type="text"
              value={node.config.trueBranch || 'Yes'}
              onChange={(e) => onChange({ ...node, config: { ...node.config, trueBranch: e.target.value } })}
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">False Branch Label</label>
            <input
              type="text"
              value={node.config.falseBranch || 'No'}
              onChange={(e) => onChange({ ...node, config: { ...node.config, falseBranch: e.target.value } })}
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>
        </>
      )}

      {node.type === 'human' && (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Prompt Message</label>
            <textarea
              value={node.config.prompt || ''}
              onChange={(e) => onChange({ ...node, config: { ...node.config, prompt: e.target.value } })}
              rows={3}
              className="w-full px-3 py-2 border rounded-md"
              placeholder="Please review and approve..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Timeout (seconds)</label>
            <input
              type="number"
              value={node.config.timeout || 3600}
              onChange={(e) => onChange({ ...node, config: { ...node.config, timeout: parseInt(e.target.value) } })}
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>
        </>
      )}
    </div>
  );
};

// Main Workflow Designer Component
export const WorkflowDesigner: React.FC = () => {
  const queryClient = useQueryClient();
  const canvasRef = useRef<HTMLDivElement>(null);

  const [workflow, setWorkflow] = useState<Workflow>({
    id: '',
    name: 'New Workflow',
    description: '',
    templateType: 'custom',
    nodes: [
      { id: 'start', type: 'start', label: 'Start', config: {}, position: { x: 400, y: 80 } },
      { id: 'end', type: 'end', label: 'End', config: {}, position: { x: 400, y: 500 } },
    ],
    edges: [],
    inputSchema: {},
    isActive: true,
  });

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  // Fetch workflows (available for future workflow list feature)
  useQuery({
    queryKey: ['workflows'],
    queryFn: async () => {
      const response = await api.get('/api/v1/workflows');
      return response.data;
    },
  });

  // Fetch templates
  const { data: templates = [] } = useQuery({
    queryKey: ['workflow-templates'],
    queryFn: async () => {
      const response = await api.get('/api/v1/templates');
      return response.data;
    },
  });

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async (wf: Workflow) => {
      const payload = {
        name: wf.name,
        description: wf.description,
        template_type: wf.templateType,
        graph_definition: {
          nodes: wf.nodes.map((n) => ({
            id: n.id,
            type: n.type,
            label: n.label,
            config: n.config,
          })),
          edges: wf.edges.map((e) => ({
            from: e.source,
            to: e.target,
            label: e.label,
            condition: e.condition,
          })),
        },
        input_schema: wf.inputSchema,
        is_active: wf.isActive,
      };

      if (wf.id) {
        return api.put(`/api/v1/workflows/${wf.id}`, payload);
      }
      return api.post('/api/v1/workflows', payload);
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      if (response.data.id) {
        setWorkflow({ ...workflow, id: response.data.id });
      }
    },
  });

  const selectedNode = workflow.nodes.find((n) => n.id === selectedNodeId);

  const handleAddNode = (type: WorkflowNode['type']) => {
    const newNode: WorkflowNode = {
      id: `node_${Date.now()}`,
      type,
      label: NODE_TYPES[type].label,
      config: {},
      position: { x: 400, y: 300 },
    };
    setWorkflow({ ...workflow, nodes: [...workflow.nodes, newNode] });
    setSelectedNodeId(newNode.id);
  };

  const handleNodeDragStart = (_nodeId: string, _e: React.DragEvent) => {
    // Drag start handler - position tracking handled in handleNodeDrag
  };

  const handleNodeDrag = (nodeId: string, e: React.DragEvent) => {
    if (e.clientX === 0 && e.clientY === 0) return; // Ignore invalid positions

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setWorkflow({
      ...workflow,
      nodes: workflow.nodes.map((n) =>
        n.id === nodeId ? { ...n, position: { x, y } } : n
      ),
    });
  };

  const handleNodeDragEnd = (_nodeId: string, _e: React.DragEvent) => {
    // Position is already updated in handleNodeDrag
  };

  const handleUpdateNode = (updatedNode: WorkflowNode) => {
    setWorkflow({
      ...workflow,
      nodes: workflow.nodes.map((n) =>
        n.id === updatedNode.id ? updatedNode : n
      ),
    });
  };

  const handleDeleteNode = (nodeId: string) => {
    if (nodeId === 'start' || nodeId === 'end') return;
    setWorkflow({
      ...workflow,
      nodes: workflow.nodes.filter((n) => n.id !== nodeId),
      edges: workflow.edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
    });
    setSelectedNodeId(null);
  };

  const handleAddEdge = (source: string, target: string) => {
    // Prevent duplicate edges
    const exists = workflow.edges.some((e) => e.source === source && e.target === target);
    if (exists) return;

    const newEdge: WorkflowEdge = {
      id: `edge_${Date.now()}`,
      source,
      target,
    };
    setWorkflow({ ...workflow, edges: [...workflow.edges, newEdge] });
  };

  const handleDeleteEdge = (edgeId: string) => {
    setWorkflow({
      ...workflow,
      edges: workflow.edges.filter((e) => e.id !== edgeId),
    });
    setSelectedEdgeId(null);
  };

  const handleLoadTemplate = (templateName: string) => {
    const template = templates.find((t: any) => t.name === templateName);
    if (!template) return;

    // Convert template to workflow format with positions
    const nodes: WorkflowNode[] = [
      { id: 'start', type: 'start', label: 'Start', config: {}, position: { x: 400, y: 80 } },
    ];
    const edges: WorkflowEdge[] = [];

    // Simple layout algorithm
    const templateNodes = template.nodes || [];
    templateNodes.forEach((nodeName: string, index: number) => {
      const y = 150 + index * 100;
      nodes.push({
        id: nodeName,
        type: 'llm',
        label: nodeName.replace(/_/g, ' '),
        config: {},
        position: { x: 400, y },
      });

      // Connect to previous node
      const prevNode = index === 0 ? 'start' : templateNodes[index - 1];
      edges.push({
        id: `edge_${index}`,
        source: prevNode,
        target: nodeName,
      });
    });

    // Add end node
    const lastY = 150 + templateNodes.length * 100;
    nodes.push({ id: 'end', type: 'end', label: 'End', config: {}, position: { x: 400, y: lastY } });

    if (templateNodes.length > 0) {
      edges.push({
        id: `edge_end`,
        source: templateNodes[templateNodes.length - 1],
        target: 'end',
      });
    }

    setWorkflow({
      ...workflow,
      name: template.name,
      description: template.description || '',
      templateType: template.name,
      nodes,
      edges,
    });
  };

  return (
    <div className="flex h-full">
      {/* Left Panel - Node Palette */}
      <div className="w-64 border-r bg-gray-50 p-4">
        <h3 className="font-semibold mb-4">Add Nodes</h3>
        <div className="space-y-2">
          {Object.entries(NODE_TYPES).map(([type, config]) => (
            type !== 'start' && type !== 'end' && (
              <button
                key={type}
                onClick={() => handleAddNode(type as WorkflowNode['type'])}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-white ${config.color} hover:opacity-90 transition-opacity`}
              >
                <span>{config.icon}</span>
                <span>{config.label}</span>
              </button>
            )
          ))}
        </div>

        <div className="mt-6">
          <h3 className="font-semibold mb-4">Load Template</h3>
          <select
            onChange={(e) => handleLoadTemplate(e.target.value)}
            className="w-full px-3 py-2 border rounded-md"
            defaultValue=""
          >
            <option value="">Select template...</option>
            {templates.map((t: any) => (
              <option key={t.name} value={t.name}>{t.name}</option>
            ))}
          </select>
        </div>

        <div className="mt-6">
          <h3 className="font-semibold mb-4">Workflow Info</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Name</label>
              <input
                type="text"
                value={workflow.name}
                onChange={(e) => setWorkflow({ ...workflow, name: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Description</label>
              <textarea
                value={workflow.description}
                onChange={(e) => setWorkflow({ ...workflow, description: e.target.value })}
                rows={2}
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
          </div>
        </div>

        <div className="mt-6">
          <button
            onClick={() => saveMutation.mutate(workflow)}
            disabled={saveMutation.isPending}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {saveMutation.isPending ? 'Saving...' : 'Save Workflow'}
          </button>
        </div>
      </div>

      {/* Canvas */}
      <div
        ref={canvasRef}
        className="flex-1 relative bg-gray-100 overflow-hidden"
        style={{ backgroundImage: 'radial-gradient(circle, #d1d5db 1px, transparent 1px)', backgroundSize: '20px 20px' }}
        onClick={() => {
          setSelectedNodeId(null);
          setSelectedEdgeId(null);
        }}
      >
        {/* SVG for edges */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none">
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="9"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="#9ca3af" />
            </marker>
          </defs>
          <g className="pointer-events-auto">
            {workflow.edges.map((edge) => {
              const sourceNode = workflow.nodes.find((n) => n.id === edge.source);
              const targetNode = workflow.nodes.find((n) => n.id === edge.target);
              if (!sourceNode || !targetNode) return null;

              return (
                <WorkflowEdgeComponent
                  key={edge.id}
                  edge={edge}
                  sourceNode={sourceNode}
                  targetNode={targetNode}
                  isSelected={selectedEdgeId === edge.id}
                  onSelect={() => {
                    setSelectedEdgeId(edge.id);
                    setSelectedNodeId(null);
                  }}
                />
              );
            })}
          </g>
        </svg>

        {/* Nodes */}
        {workflow.nodes.map((node) => (
          <WorkflowNodeComponent
            key={node.id}
            node={node}
            isSelected={selectedNodeId === node.id}
            onSelect={() => {
              setSelectedNodeId(node.id);
              setSelectedEdgeId(null);
            }}
            onDragStart={(e) => handleNodeDragStart(node.id, e)}
            onDrag={(e) => handleNodeDrag(node.id, e)}
            onDragEnd={(e) => handleNodeDragEnd(node.id, e)}
          />
        ))}

        {/* Quick connect hint */}
        <div className="absolute bottom-4 left-4 bg-white px-4 py-2 rounded-lg shadow text-sm text-gray-600">
          Tip: Drag nodes to position. Click a node to edit properties.
        </div>
      </div>

      {/* Right Panel - Properties */}
      <div className="w-80 border-l bg-white">
        <div className="border-b px-4 py-3">
          <h3 className="font-semibold">Properties</h3>
        </div>

        {selectedNode ? (
          <NodePropertiesPanel
            node={selectedNode}
            onChange={handleUpdateNode}
            onDelete={() => handleDeleteNode(selectedNode.id)}
          />
        ) : selectedEdgeId ? (
          <div className="p-4 space-y-4">
            <h3 className="font-semibold">Edge Properties</h3>
            {(() => {
              const edge = workflow.edges.find((e) => e.id === selectedEdgeId);
              if (!edge) return null;
              return (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Label</label>
                    <input
                      type="text"
                      value={edge.label || ''}
                      onChange={(e) => setWorkflow({
                        ...workflow,
                        edges: workflow.edges.map((ed) =>
                          ed.id === edge.id ? { ...ed, label: e.target.value } : ed
                        ),
                      })}
                      className="w-full px-3 py-2 border rounded-md"
                      placeholder="Optional label"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Condition</label>
                    <input
                      type="text"
                      value={edge.condition || ''}
                      onChange={(e) => setWorkflow({
                        ...workflow,
                        edges: workflow.edges.map((ed) =>
                          ed.id === edge.id ? { ...ed, condition: e.target.value } : ed
                        ),
                      })}
                      className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                      placeholder="e.g., state.approved == true"
                    />
                  </div>
                  <button
                    onClick={() => handleDeleteEdge(edge.id)}
                    className="text-red-500 hover:text-red-700"
                  >
                    Delete Edge
                  </button>
                </>
              );
            })()}
          </div>
        ) : (
          <div className="p-4 text-gray-500 text-center">
            <p>Select a node or edge to edit its properties</p>
          </div>
        )}

        {/* Connection Tools */}
        {selectedNodeId && selectedNodeId !== 'end' && (
          <div className="border-t p-4">
            <h4 className="font-medium text-sm mb-2">Connect to:</h4>
            <div className="flex flex-wrap gap-2">
              {workflow.nodes
                .filter((n) => n.id !== selectedNodeId && n.id !== 'start')
                .map((n) => (
                  <button
                    key={n.id}
                    onClick={() => handleAddEdge(selectedNodeId, n.id)}
                    className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
                  >
                    {n.label}
                  </button>
                ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default WorkflowDesigner;
