use super::*;

#[derive(Clone, Debug, PartialEq)]
pub(super) enum ProjectCommand {
    List,
    Get(String),
    Create(client::ProjectCreateRequest),
    Update(String, client::ProjectUpdateRequest),
    Delete(String),
}

pub(super) fn parse(mut args: Arguments) -> Result<ProjectCommand, CliError> {
    let operation = args.required_positional("project subcommand")?;
    if operation == "list" {
        parse_no_options(&mut args, "project list", help())?;
        return Ok(ProjectCommand::List);
    }
    let value = args.required_positional(if operation == "create" {
        "Project name"
    } else {
        "Project ID"
    })?;
    if matches!(operation.as_str(), "get" | "delete") {
        parse_no_options(&mut args, "project", help())?;
        return Ok(if operation == "get" {
            ProjectCommand::Get(value)
        } else {
            ProjectCommand::Delete(value)
        });
    }
    if !matches!(operation.as_str(), "create" | "update") {
        return Err(CliError::Message("Unknown project subcommand".into()));
    }
    let mut name = None;
    let mut id = None;
    let mut model = None;
    let mut effort = "medium".to_owned();
    let mut speed = "standard".to_owned();
    let mut clear_model = false;
    while let Some((option, inline)) = args.pop_option()? {
        match option.as_str() {
            "--name" if operation == "update" => name = Some(args.option_value(&option, inline)?),
            "--id" if operation == "create" => id = Some(args.option_value(&option, inline)?),
            "--model" => model = Some(args.option_value(&option, inline)?),
            "--effort" => effort = args.option_value(&option, inline)?,
            "--speed" => speed = args.option_value(&option, inline)?,
            "--clear-model" if operation == "update" => {
                args.flag(&option, inline)?;
                clear_model = true;
            }
            "--help" | "-h" => return Err(CliError::Help(help())),
            _ => return Err(args.unknown_option(&option, "project")),
        }
    }
    if clear_model && model.is_some() {
        return Err(CliError::Message(
            "--clear-model cannot be combined with --model".into(),
        ));
    }
    let model = model.map(|model_id| client::ProjectModel {
        model_id,
        effort,
        speed,
    });
    if operation == "create" {
        Ok(ProjectCommand::Create(client::ProjectCreateRequest {
            id,
            name: value,
            model,
        }))
    } else {
        Ok(ProjectCommand::Update(
            value,
            client::ProjectUpdateRequest {
                name,
                model: if clear_model {
                    Change::Clear
                } else if let Some(model) = model {
                    Change::Set(model)
                } else {
                    Change::Unchanged
                },
            },
        ))
    }
}

pub(super) fn execute(command: ProjectCommand, client: &RelClient) -> Result<i32, CliError> {
    match command {
        ProjectCommand::List => print_json(&client.list_projects()?)?,
        ProjectCommand::Get(id) => print_json(&client.get_project(&id)?)?,
        ProjectCommand::Create(request) => print_json(&client.create_project(&request)?)?,
        ProjectCommand::Update(id, request) => print_json(&client.update_project(&id, &request)?)?,
        ProjectCommand::Delete(id) => print_json(&client.delete_project(&id)?)?,
    }
    Ok(0)
}

pub(super) fn parse_session_action(
    mut args: Arguments,
    is_move: bool,
) -> Result<CliCommand, CliError> {
    let id = args.required_positional("Session ID")?;
    let mut project_id = None;
    let mut profile_id = None;
    let mut include_shared_sessions = false;
    while let Some((option, inline)) = args.pop_option()? {
        match option.as_str() {
            "--project-id" if is_move => set_once(
                &mut project_id,
                args.option_value(&option, inline)?,
                &option,
            )?,
            "--profile-id" if !is_move => set_once(
                &mut profile_id,
                args.option_value(&option, inline)?,
                &option,
            )?,
            "--include-shared-sessions" => {
                args.flag(&option, inline)?;
                include_shared_sessions = true;
            }
            _ => return Err(args.unknown_option(&option, "session")),
        }
    }
    if is_move {
        Ok(CliCommand::SessionMove(
            id,
            client::SessionMoveRequest {
                project_id: project_id
                    .ok_or_else(|| CliError::Message("--project-id is required".into()))?,
                include_shared_sessions,
            },
        ))
    } else {
        Ok(CliCommand::SessionReapply(
            id,
            client::SessionReapplyRequest {
                profile_id,
                include_shared_sessions,
            },
        ))
    }
}

pub(super) fn help() -> String {
    "Usage: rel project list|get ID|create NAME [--id ID] [--model ID]|update ID [--name NAME] [--model ID|--clear-model]|delete ID\nSession creation requires --project-id ID. Use rel session move ID --project-id ID or rel session reapply ID [--profile-id ID].\n".into()
}
