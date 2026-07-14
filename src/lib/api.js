export function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }

  return data;
}

export async function fetchOptions() {
  return requestJson("/api/options");
}

export async function fetchProjects() {
  return requestJson("/api/projects");
}

export async function fetchProject(projectId) {
  return requestJson(`/api/projects/${projectId}`);
}

export async function deleteProject(projectId) {
  return requestJson(`/api/projects/${projectId}`, {
    method: "DELETE",
  });
}

export async function analyzeFile({ file, extraPrompt, root, scaleType, separateVocals = false }) {
  const fileData = await readFileAsDataUrl(file);

  return requestJson("/api/analyze", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      filename: file.name,
      file_data: fileData,
      extra_prompt: extraPrompt,
      root,
      scale_type: scaleType,
      separate_vocals: separateVocals,
    }),
  });
}

export async function askFollowUp(projectId, question) {
  return requestJson("/api/follow-up", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      project_id: projectId,
      question,
    }),
  });
}
