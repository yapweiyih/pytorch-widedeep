import numpy as np
import torch
import pandas as pd

from pytorch_widedeep.optim import RAdam
from pytorch_widedeep.models import Wide, WideDeep, DeepDense, DeepDenseResnet
from pytorch_widedeep.metrics import Accuracy, Precision
from pytorch_widedeep.callbacks import (
    LRHistory,
    EarlyStopping,
    ModelCheckpoint,
)
from pytorch_widedeep.initializers import XavierNormal, KaimingNormal
from pytorch_widedeep.preprocessing import WidePreprocessor, DensePreprocessor
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

use_cuda = torch.cuda.is_available()

if __name__ == "__main__":
    colnames = [
        "age",
        "workclass",
        "fnlwgt",
        "education",
        "education-num",
        "marital-status",
        "occupation",
        "relationship",
        "race",
        "gender",
        "capital-gain",
        "capital-loss",
        "hours-per-week",
        "native-country",
        "income",
    ]
    df = pd.read_csv("data/adult/adult.csv", names=colnames, index_col=False)
    df.columns = [c.replace("-", "_") for c in df.columns]

    df["age_buckets"] = pd.cut(df.age, bins=[16, 25, 30, 35, 40, 45, 50, 55, 60, 91], labels=np.arange(9))
    df["income_label"] = (df["income"].apply(lambda x: ">50K" in x)).astype(int)
    df.drop("income", axis=1, inplace=True)
    df.head()

    wide_cols = [
        "age_buckets",
        "education",
        "relationship",
        "workclass",
        "occupation",
        "native_country",
        "gender",
    ]
    crossed_cols = [("education", "occupation"), ("native_country", "occupation")]
    cat_embed_cols = [
        ("education", 10),
        ("relationship", 8),
        ("workclass", 10),
        ("occupation", 10),
        ("native_country", 10),
    ]
    continuous_cols = ["age", "hours_per_week"]
    target = "income_label"
    target = df[target].values
    prepare_wide = WidePreprocessor(wide_cols=wide_cols, crossed_cols=crossed_cols)
    X_wide = prepare_wide.fit_transform(df)
    prepare_deep = DensePreprocessor(
        embed_cols=cat_embed_cols, continuous_cols=continuous_cols  # type: ignore[arg-type]
    )
    X_deep = prepare_deep.fit_transform(df)

    wide = Wide(wide_dim=np.unique(X_wide).shape[0], pred_dim=1)

    deepdense = DeepDense(
        hidden_layers=[64, 32],
        dropout=[0.2, 0.2],
        deep_column_idx=prepare_deep.deep_column_idx,
        embed_input=prepare_deep.embeddings_input,
        continuous_cols=continuous_cols,
    )

    # # To use DeepDenseResnet as the deepdense component simply:
    # deepdense = DeepDenseResnet(
    #     blocks=[64, 32],
    #     deep_column_idx=prepare_deep.deep_column_idx,
    #     embed_input=prepare_deep.embeddings_input,
    #     continuous_cols=continuous_cols,
    # )

    model = WideDeep(wide=wide, deepdense=deepdense)

    wide_opt = torch.optim.Adam(model.wide.parameters(), lr=0.01)
    deep_opt = RAdam(model.deepdense.parameters())
    wide_sch = torch.optim.lr_scheduler.StepLR(wide_opt, step_size=3)
    deep_sch = torch.optim.lr_scheduler.StepLR(deep_opt, step_size=5)

    optimizers = {"wide": wide_opt, "deepdense": deep_opt}
    schedulers = {"wide": wide_sch, "deepdense": deep_sch}
    initializers = {"wide": KaimingNormal, "deepdense": XavierNormal}
    callbacks = [
        LRHistory(n_epochs=10),
        EarlyStopping(patience=5),
        ModelCheckpoint(filepath="model_weights/wd_out"),
    ]
    metrics = [Accuracy, Precision]

    model.compile(
        method="binary",
        optimizers=optimizers,
        lr_schedulers=schedulers,
        initializers=initializers,
        callbacks=callbacks,
        metrics=metrics,
    )

    X_wide_train, X_wide_test, X_deep_train, X_deep_test, y_train, y_test = train_test_split(
        X_wide, X_deep, target, test_size=0.2
    )

    model.fit(
        X_wide=X_wide_train, X_deep=X_deep_train, target=y_train, n_epochs=4, batch_size=64, val_split=0.2,
    )
    # # to save/load the model
    # torch.save(model, "model_weights/model.t")
    # model = torch.load("model_weights/model.t")

    preds = model.predict(X_wide_test, X_deep_test)
    accuracy = accuracy_score(y_test, preds)
    print(accuracy)
    # # to save/load the model
    # torch.save(model, "model_weights/model.t")
    # model = torch.load("model_weights/model.t")

    # # or via state dictionaries
    # torch.save(model.state_dict(), "model_weights/model_dict.t")
    # model = WideDeep(wide=wide, deepdense=deepdense)
    # model.load_state_dict(torch.load("model_weights/model_dict.t"))
    # # <All keys matched successfully>
