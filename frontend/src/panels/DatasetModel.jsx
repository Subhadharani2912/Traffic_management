export default function DatasetModel({ status, onNotify }) {
  const meta = status.dataset || {}
  const model = status.model || {}
  const splits = meta.processed_splits || {}

  const card = (label, value, note) => (
    <div className="summary-card" key={label}>
      <span>{label}</span>
      <strong>{value ?? '—'}</strong>
      <small>{note || ''}</small>
    </div>
  )

  return (
    <div className="dataset-page">
      <section className="summary-grid">
        {card('Model', model.active_model || 'yolov8n.pt', model.status || '')}
        {card('Custom trained', model.is_custom_trained ? 'YES' : 'NO', model.is_custom_trained ? 'custom model active' : 'standard model in use')}
        {card('Confidence', model.confidence_threshold ?? '—', 'detection threshold')}
        {card('Dataset', meta.status || '—', meta.name || 'Traffic dataset')}
        {card('Train images', splits.train ?? '—', 'for training')}
        {card('Val images', splits.val ?? '—', 'for evaluation')}
        {card('Test images', splits.test ?? '—', 'unseen')}
      </section>

      <section className="analytics-panel">
        <h3>Training pipeline</h3>
        <ol className="pipeline-list">
          <li>
            <b>Prepare data</b> — converts the dataset annotations into the training format and splits the images into
            train / val / test sets. Split status currently: train {splits.train ?? 0} · val {splits.val ?? 0} · test {splits.test ?? 0}
            {splits.yaml_created ? ' · data file ready' : ''}.
          </li>
          <li>
            <b>Train</b> — trains a YOLO model with the chosen settings; the fitted model lands in the models folder and
            becomes the active detector automatically.
          </li>
          <li>
            <b>Evaluate</b> — measures accuracy of the trained model and reports it on the Vehicle Detection page.
          </li>
        </ol>
        <div className="hint">The engine uses the standard pre-trained YOLOv8n until a custom model is trained.</div>
      </section>
    </div>
  )
}