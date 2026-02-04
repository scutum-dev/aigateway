import React, { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';

interface PolicyRule {
  id: string;
  name: string;
  description: string;
  priority: number;
  condition: PolicyCondition;
  action: 'permit' | 'deny';
  targetModels: string[];
  isActive: boolean;
}

interface PolicyCondition {
  type: 'and' | 'or' | 'comparison';
  field?: string;
  operator?: '<' | '>' | '<=' | '>=' | '==' | '!=';
  value?: string | number | boolean;
  children?: PolicyCondition[];
}

interface Model {
  model_id: string;
  provider: string;
  tier: string;
}

const CONDITION_FIELDS = [
  { value: 'context.budget_remaining', label: 'Budget Remaining ($)' },
  { value: 'context.latency_sla_ms', label: 'Latency SLA (ms)' },
  { value: 'context.error_rate', label: 'Error Rate (%)' },
  { value: 'resource.tier', label: 'Model Tier' },
  { value: 'resource.provider', label: 'Provider' },
  { value: 'resource.cost_per_1k', label: 'Cost per 1K tokens' },
  { value: 'principal.team', label: 'Team' },
  { value: 'principal.role', label: 'Role' },
];

const OPERATORS = [
  { value: '<', label: 'Less than' },
  { value: '>', label: 'Greater than' },
  { value: '<=', label: 'Less than or equal' },
  { value: '>=', label: 'Greater than or equal' },
  { value: '==', label: 'Equals' },
  { value: '!=', label: 'Not equals' },
];

// Condition Builder Component
const ConditionBuilder: React.FC<{
  condition: PolicyCondition;
  onChange: (condition: PolicyCondition) => void;
  onRemove?: () => void;
  depth?: number;
}> = ({ condition, onChange, onRemove, depth = 0 }) => {
  const isGroup = condition.type === 'and' || condition.type === 'or';

  const handleAddCondition = () => {
    if (!condition.children) return;
    onChange({
      ...condition,
      children: [
        ...condition.children,
        { type: 'comparison', field: 'context.budget_remaining', operator: '>', value: 0 },
      ],
    });
  };

  const handleAddGroup = () => {
    if (!condition.children) return;
    onChange({
      ...condition,
      children: [
        ...condition.children,
        { type: 'and', children: [] },
      ],
    });
  };

  const handleChildChange = (index: number, newChild: PolicyCondition) => {
    if (!condition.children) return;
    const newChildren = [...condition.children];
    newChildren[index] = newChild;
    onChange({ ...condition, children: newChildren });
  };

  const handleChildRemove = (index: number) => {
    if (!condition.children) return;
    onChange({
      ...condition,
      children: condition.children.filter((_, i) => i !== index),
    });
  };

  if (isGroup) {
    return (
      <div className={`border rounded-lg p-4 ${depth > 0 ? 'ml-4 bg-gray-50' : 'bg-white'}`}>
        <div className="flex items-center gap-4 mb-4">
          <select
            value={condition.type}
            onChange={(e) => onChange({ ...condition, type: e.target.value as 'and' | 'or' })}
            className="px-3 py-2 border rounded-md font-medium bg-blue-50 text-blue-700"
          >
            <option value="and">ALL of (AND)</option>
            <option value="or">ANY of (OR)</option>
          </select>
          <span className="text-gray-500 text-sm">
            {condition.type === 'and' ? 'All conditions must match' : 'At least one condition must match'}
          </span>
          {onRemove && (
            <button
              onClick={onRemove}
              className="ml-auto text-red-500 hover:text-red-700"
              title="Remove group"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
        </div>

        <div className="space-y-3">
          {condition.children?.map((child, index) => (
            <ConditionBuilder
              key={index}
              condition={child}
              onChange={(newChild) => handleChildChange(index, newChild)}
              onRemove={() => handleChildRemove(index)}
              depth={depth + 1}
            />
          ))}
        </div>

        <div className="flex gap-2 mt-4">
          <button
            onClick={handleAddCondition}
            className="px-3 py-1 text-sm border border-blue-300 text-blue-600 rounded hover:bg-blue-50"
          >
            + Add Condition
          </button>
          <button
            onClick={handleAddGroup}
            className="px-3 py-1 text-sm border border-purple-300 text-purple-600 rounded hover:bg-purple-50"
          >
            + Add Group
          </button>
        </div>
      </div>
    );
  }

  // Comparison condition
  return (
    <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
      <select
        value={condition.field || ''}
        onChange={(e) => onChange({ ...condition, field: e.target.value })}
        className="px-3 py-2 border rounded-md flex-1"
      >
        {CONDITION_FIELDS.map((field) => (
          <option key={field.value} value={field.value}>{field.label}</option>
        ))}
      </select>

      <select
        value={condition.operator || '=='}
        onChange={(e) => onChange({ ...condition, operator: e.target.value as any })}
        className="px-3 py-2 border rounded-md"
      >
        {OPERATORS.map((op) => (
          <option key={op.value} value={op.value}>{op.label}</option>
        ))}
      </select>

      <input
        type="text"
        value={condition.value?.toString() || ''}
        onChange={(e) => {
          const val = e.target.value;
          // Try to parse as number
          const numVal = parseFloat(val);
          onChange({
            ...condition,
            value: isNaN(numVal) ? val : numVal,
          });
        }}
        placeholder="Value"
        className="px-3 py-2 border rounded-md w-32"
      />

      {onRemove && (
        <button
          onClick={onRemove}
          className="text-red-500 hover:text-red-700 p-1"
          title="Remove condition"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
};

// Cedar Code Preview
const CedarPreview: React.FC<{ policy: PolicyRule }> = ({ policy }) => {
  const generateCedar = useCallback((policy: PolicyRule): string => {
    const lines: string[] = [];

    // Add annotation
    lines.push(`@priority(${policy.priority})`);

    // Action
    lines.push(`${policy.action} (`);
    lines.push(`    principal,`);
    lines.push(`    action == "routing:select_model",`);
    lines.push(`    resource`);
    lines.push(`)`);

    // Condition
    if (policy.condition.children && policy.condition.children.length > 0) {
      lines.push(`when {`);
      lines.push(`    ${conditionToCedar(policy.condition)}`);
      lines.push(`};`);
    } else {
      lines.push(`;`);
    }

    return lines.join('\n');
  }, []);

  const conditionToCedar = (condition: PolicyCondition): string => {
    if (condition.type === 'comparison') {
      return `${condition.field} ${condition.operator} ${JSON.stringify(condition.value)}`;
    }

    const operator = condition.type === 'and' ? ' &&\n    ' : ' ||\n    ';
    const children = condition.children?.map((c) => conditionToCedar(c)) || [];
    return children.join(operator);
  };

  return (
    <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
      <div className="flex items-center justify-between mb-2">
        <span className="text-gray-400 text-sm">Cedar Policy Preview</span>
        <button
          onClick={() => navigator.clipboard.writeText(generateCedar(policy))}
          className="text-gray-400 hover:text-white text-sm"
        >
          Copy
        </button>
      </div>
      <pre className="text-green-400 font-mono text-sm whitespace-pre">
        {generateCedar(policy)}
      </pre>
    </div>
  );
};

// Main Policy Editor Component
export const PolicyEditor: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedPolicy, setSelectedPolicy] = useState<PolicyRule | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  // Fetch policies
  const { data: policies = [], isLoading } = useQuery({
    queryKey: ['routing-policies'],
    queryFn: async () => {
      const response = await api.get('/api/v1/routing-policies');
      return response.data;
    },
  });

  // Fetch models for target selection
  const { data: models = [] } = useQuery<Model[]>({
    queryKey: ['models'],
    queryFn: async () => {
      const response = await api.get('/api/v1/models');
      return response.data;
    },
  });

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async (policy: PolicyRule) => {
      if (policy.id) {
        return api.put(`/api/v1/routing-policies/${policy.id}`, policy);
      }
      return api.post('/api/v1/routing-policies', policy);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['routing-policies'] });
      setSelectedPolicy(null);
      setIsCreating(false);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      return api.delete(`/api/v1/routing-policies/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['routing-policies'] });
      setSelectedPolicy(null);
    },
  });

  const handleCreateNew = () => {
    setSelectedPolicy({
      id: '',
      name: 'New Policy',
      description: '',
      priority: 50,
      condition: { type: 'and', children: [] },
      action: 'permit',
      targetModels: [],
      isActive: true,
    });
    setIsCreating(true);
  };

  const handleSave = () => {
    if (selectedPolicy) {
      saveMutation.mutate(selectedPolicy);
    }
  };

  if (isLoading) {
    return <div className="p-6">Loading policies...</div>;
  }

  return (
    <div className="flex h-full">
      {/* Policy List Sidebar */}
      <div className="w-80 border-r bg-gray-50 p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Routing Policies</h2>
          <button
            onClick={handleCreateNew}
            className="px-3 py-1 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700"
          >
            + New
          </button>
        </div>

        <div className="space-y-2">
          {policies.map((policy: PolicyRule) => (
            <div
              key={policy.id}
              onClick={() => {
                setSelectedPolicy(policy);
                setIsCreating(false);
              }}
              className={`p-3 rounded-lg cursor-pointer transition-colors ${
                selectedPolicy?.id === policy.id
                  ? 'bg-blue-100 border-blue-300 border'
                  : 'bg-white border border-gray-200 hover:border-blue-200'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium">{policy.name}</span>
                <span className={`px-2 py-0.5 text-xs rounded ${
                  policy.action === 'permit'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-red-100 text-red-700'
                }`}>
                  {policy.action}
                </span>
              </div>
              <div className="text-sm text-gray-500 mt-1">Priority: {policy.priority}</div>
              {!policy.isActive && (
                <div className="text-xs text-yellow-600 mt-1">Disabled</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Policy Editor */}
      <div className="flex-1 p-6 overflow-y-auto">
        {selectedPolicy ? (
          <div className="max-w-4xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold">
                {isCreating ? 'Create Policy' : 'Edit Policy'}
              </h2>
              <div className="flex gap-2">
                {!isCreating && (
                  <button
                    onClick={() => deleteMutation.mutate(selectedPolicy.id)}
                    className="px-4 py-2 text-red-600 border border-red-300 rounded-md hover:bg-red-50"
                  >
                    Delete
                  </button>
                )}
                <button
                  onClick={() => {
                    setSelectedPolicy(null);
                    setIsCreating(false);
                  }}
                  className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={saveMutation.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {saveMutation.isPending ? 'Saving...' : 'Save Policy'}
                </button>
              </div>
            </div>

            {/* Basic Info */}
            <div className="bg-white rounded-lg border p-6 mb-6">
              <h3 className="text-lg font-semibold mb-4">Basic Information</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Policy Name
                  </label>
                  <input
                    type="text"
                    value={selectedPolicy.name}
                    onChange={(e) => setSelectedPolicy({ ...selectedPolicy, name: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Priority (0-100)
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={selectedPolicy.priority}
                    onChange={(e) => setSelectedPolicy({ ...selectedPolicy, priority: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    value={selectedPolicy.description}
                    onChange={(e) => setSelectedPolicy({ ...selectedPolicy, description: e.target.value })}
                    rows={2}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Action
                  </label>
                  <select
                    value={selectedPolicy.action}
                    onChange={(e) => setSelectedPolicy({ ...selectedPolicy, action: e.target.value as 'permit' | 'deny' })}
                    className="w-full px-3 py-2 border rounded-md"
                  >
                    <option value="permit">Permit (Allow)</option>
                    <option value="deny">Deny (Block)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Status
                  </label>
                  <label className="flex items-center gap-2 mt-2">
                    <input
                      type="checkbox"
                      checked={selectedPolicy.isActive}
                      onChange={(e) => setSelectedPolicy({ ...selectedPolicy, isActive: e.target.checked })}
                      className="w-4 h-4"
                    />
                    <span>Policy is active</span>
                  </label>
                </div>
              </div>
            </div>

            {/* Target Models */}
            <div className="bg-white rounded-lg border p-6 mb-6">
              <h3 className="text-lg font-semibold mb-4">Target Models</h3>
              <p className="text-gray-500 text-sm mb-4">
                Select which models this policy applies to. Leave empty to apply to all models.
              </p>
              <div className="grid grid-cols-3 gap-2">
                {models.map((model) => (
                  <label key={model.model_id} className="flex items-center gap-2 p-2 border rounded hover:bg-gray-50">
                    <input
                      type="checkbox"
                      checked={selectedPolicy.targetModels.includes(model.model_id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedPolicy({
                            ...selectedPolicy,
                            targetModels: [...selectedPolicy.targetModels, model.model_id],
                          });
                        } else {
                          setSelectedPolicy({
                            ...selectedPolicy,
                            targetModels: selectedPolicy.targetModels.filter((m) => m !== model.model_id),
                          });
                        }
                      }}
                      className="w-4 h-4"
                    />
                    <span className="text-sm">{model.model_id}</span>
                    <span className="text-xs text-gray-400 ml-auto">{model.tier}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Conditions */}
            <div className="bg-white rounded-lg border p-6 mb-6">
              <h3 className="text-lg font-semibold mb-4">Conditions</h3>
              <p className="text-gray-500 text-sm mb-4">
                Define when this policy should be applied using conditions.
              </p>
              <ConditionBuilder
                condition={selectedPolicy.condition}
                onChange={(condition) => setSelectedPolicy({ ...selectedPolicy, condition })}
              />
            </div>

            {/* Cedar Preview */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold mb-4">Generated Cedar Policy</h3>
              <CedarPreview policy={selectedPolicy} />
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-lg">Select a policy to edit</p>
              <p className="text-sm">or create a new one</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PolicyEditor;
