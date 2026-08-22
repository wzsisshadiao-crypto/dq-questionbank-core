Attribute VB_Name = "DQWordPublishing"
Option Explicit

' DQ QuestionBank Core public Word client.
' The macro sends reviewed, digest-bound block metadata to a loopback bridge.
' It never sends credentials, opens remote URLs, or executes document content.
Private Const DQ_PROTOCOL As String = "0.2"
Private Const DQ_DEFAULT_ORIGIN As String = "http://127.0.0.1:8766"
Private Const DQ_TAG_PREFIX As String = "dqwb:"

Private Function IsManaged(ByVal cc As ContentControl) As Boolean
    IsManaged = (Left$(CStr(cc.Tag), Len(DQ_TAG_PREFIX)) = DQ_TAG_PREFIX)
End Function

Private Function BlockId(ByVal cc As ContentControl) As String
    Dim fields() As String
    fields = Split(Mid$(cc.Tag, Len(DQ_TAG_PREFIX) + 1), "|")
    If UBound(fields) >= 0 Then BlockId = fields(0)
End Function

Private Function QuestionId(ByVal cc As ContentControl) As String
    Dim fields() As String
    fields = Split(Mid$(cc.Tag, Len(DQ_TAG_PREFIX) + 1), "|")
    If UBound(fields) >= 1 Then QuestionId = fields(1)
End Function

Private Function Fingerprint(ByVal cc As ContentControl) As String
    Dim fields() As String
    fields = Split(Mid$(cc.Tag, Len(DQ_TAG_PREFIX) + 1), "|")
    If UBound(fields) >= 2 Then Fingerprint = fields(2)
End Function

Private Function JsonEscape(ByVal value As String) As String
    JsonEscape = Replace(Replace(Replace(value, "\", "\"), Chr$(34), "\" & Chr$(34)), vbCrLf, "\n")
    JsonEscape = Replace(JsonEscape, vbCr, "\n")
    JsonEscape = Replace(JsonEscape, vbLf, "\n")
End Function

Private Function BridgeRequest(ByVal path As String, ByVal body As String) As String
    Dim http As Object
    Set http = CreateObject("MSXML2.XMLHTTP.6.0")
    http.Open "POST", DQ_DEFAULT_ORIGIN & path, False
    http.SetRequestHeader "Content-Type", "application/json"
    http.SetRequestHeader "X-DQ-Word-Protocol", DQ_PROTOCOL
    http.Send body
    If http.Status < 200 Or http.Status >= 300 Then
        Err.Raise vbObjectError + 710, "DQWordPublishing", "Bridge rejected request: " & CStr(http.Status) & " " & http.ResponseText
    End If
    BridgeRequest = CStr(http.ResponseText)
End Function

Public Sub DQ_CheckBridge()
    Dim http As Object
    On Error GoTo BridgeUnavailable
    Set http = CreateObject("MSXML2.XMLHTTP.6.0")
    http.Open "GET", DQ_DEFAULT_ORIGIN & "/status", False
    http.Send
    If http.Status = 200 And InStr(1, http.ResponseText, """protocol"":""" & DQ_PROTOCOL & """", vbTextCompare) > 0 Then
        MsgBox "DQ Word publishing bridge is ready.", vbInformation
        Exit Sub
    End If
BridgeUnavailable:
    MsgBox "DQ Word publishing bridge is unavailable or incompatible.", vbExclamation
End Sub

Private Function JsonString(ByVal jsonText As String, ByVal key As String) As String
    Dim marker As String
    Dim valueStart As Long
    Dim index As Long
    Dim current As String
    Dim output As String
    Dim escaped As Boolean
    marker = Chr$(34) & key & Chr$(34) & ":" & Chr$(34)
    valueStart = InStr(1, jsonText, marker, vbBinaryCompare)
    If valueStart = 0 Then Exit Function
    valueStart = valueStart + Len(marker)
    For index = valueStart To Len(jsonText)
        current = Mid$(jsonText, index, 1)
        If escaped Then
            Select Case current
                Case "n": output = output & vbCrLf
                Case "r": output = output & vbCr
                Case "t": output = output & vbTab
                Case Chr$(34): output = output & Chr$(34)
                Case "\": output = output & "\"
                Case Else: output = output & current
            End Select
            escaped = False
        ElseIf current = "\" Then
            escaped = True
        ElseIf current = Chr$(34) Then
            Exit For
        Else
            output = output & current
        End If
    Next index
    JsonString = output
End Function

Private Function CurrentBlockJson(ByVal cc As ContentControl) As String
    CurrentBlockJson = "{""block_id"":""" & JsonEscape(BlockId(cc)) & "",""question_id"":""" & JsonEscape(QuestionId(cc)) & "",""question_fingerprint"":""" & JsonEscape(Fingerprint(cc)) & "",""content"":""" & JsonEscape(cc.Range.Text) & """}"
End Function

Private Function RefreshOne(ByVal cc As ContentControl, ByVal mode As String) As Boolean
    Dim envelope As String
    Dim response As String
    Dim oldText As String
    oldText = cc.Range.Text
    envelope = "{""envelope_version"":""" & DQ_PROTOCOL & "",""document_id"":""word-" & JsonEscape(ActiveDocument.Name) & "",""mode"":""" & mode & "",""service_origin"":""" & DQ_DEFAULT_ORIGIN & "",""blocks":[{" & _
        """block_id"":""" & JsonEscape(BlockId(cc)) & "",""question_id"":""" & JsonEscape(QuestionId(cc)) & "",""question_fingerprint"":""" & JsonEscape(Fingerprint(cc)) & "",""roles"":[""stem"",""choices"",""answer"",""solution""],""display"":{}}]," & _
        """refresh"":{""strategy"":""explicit"",""on_missing"":""stale"",""on_revision_mismatch"":""stale""}," & _
        """rollback"":{""scope"":""single-block"",""on_failure"":""restore-previous-block""}," & _
        """security"":{""allowed_origins"":[""" & DQ_DEFAULT_ORIGIN & """],""remote_origins"":[],""credentials"":""never""}}"
    On Error GoTo RestoreBlock
    response = BridgeRequest("/v1/refresh", "{""envelope"":" & envelope & ",""current":{""" & JsonEscape(BlockId(cc)) & "":" & CurrentBlockJson(cc) & "}}")
    If InStr(1, response, """status"":""refreshed""", vbTextCompare) = 0 Then GoTo RestoreBlock
    cc.Range.Text = JsonString(response, "content")
    RefreshOne = True
    Exit Function
RestoreBlock:
    cc.Range.Text = oldText
    RefreshOne = False
End Function

Private Function SelectedManagedControl() As ContentControl
    Dim cc As ContentControl
    For Each cc In ActiveDocument.ContentControls
        If IsManaged(cc) Then
            If Selection.Range.Start >= cc.Range.Start And Selection.Range.End <= cc.Range.End Then
                Set SelectedManagedControl = cc
                Exit Function
            End If
        End If
    Next cc
End Function

Public Sub DQ_InsertReferenceBlock()
    Dim cc As ContentControl
    Dim blockId As String
    Dim questionId As String
    Dim response As String
    Dim fingerprintValue As String
    questionId = Trim$(InputBox("Question id", "DQ Word publishing"))
    If questionId = "" Then Exit Sub
    blockId = "block-" & Format$(Now, "yyyymmddhhnnss")
    Set cc = ActiveDocument.ContentControls.Add(wdContentControlRichText, Selection.Range)
    cc.Title = "DQ managed reference block"
    cc.Tag = DQ_TAG_PREFIX & blockId & "|" & questionId & "|sha256:pending"
    cc.Range.Text = "Resolving reviewed question..."
    On Error GoTo InsertFailed
    response = BridgeRequest("/v1/insert", "{""block_id"":""" & JsonEscape(blockId) & "",""question_id"":""" & JsonEscape(questionId) & "",""mode"":""compose""}")
    fingerprintValue = JsonString(response, "question_fingerprint")
    If fingerprintValue = "" Then GoTo InsertFailed
    cc.Tag = DQ_TAG_PREFIX & blockId & "|" & questionId & "|" & fingerprintValue
    cc.Range.Text = JsonString(response, "content")
    Exit Sub
InsertFailed:
    cc.Range.Text = "Stale: question was not inserted; start the local bridge and retry."
End Sub

Public Sub DQ_RefreshCurrentBlock()
    Dim cc As ContentControl
    Set cc = SelectedManagedControl()
    If cc Is Nothing Then
        MsgBox "Place the cursor inside a managed DQ block first.", vbInformation
        Exit Sub
    End If
    If Not RefreshOne(cc, "compose") Then MsgBox "Block was kept unchanged (stale or failed).", vbExclamation
End Sub

Public Sub DQ_RefreshAllBlocks()
    Dim cc As ContentControl
    Dim failures As Long
    For Each cc In ActiveDocument.ContentControls
        If IsManaged(cc) Then If Not RefreshOne(cc, "compose") Then failures = failures + 1
    Next cc
    If failures > 0 Then MsgBox CStr(failures) & " block(s) stayed unchanged.", vbExclamation
End Sub

Public Sub DQ_ShowComposeBlocks()
    Dim cc As ContentControl
    For Each cc In ActiveDocument.ContentControls
        If IsManaged(cc) Then cc.Appearance = wdContentControlBoundingBox
    Next cc
End Sub

Public Sub DQ_RenderFinal()
    Dim cc As ContentControl
    Dim refreshed As Collection
    Set refreshed = New Collection
    For Each cc In ActiveDocument.ContentControls
        If IsManaged(cc) Then
            If Not RefreshOne(cc, "final") Then GoTo FinalFailed
            refreshed.Add cc
        End If
    Next cc
    For Each cc In refreshed
        cc.Appearance = wdContentControlHidden
    Next cc
    ActiveDocument.Save
    Exit Sub
FinalFailed:
    For Each cc In ActiveDocument.ContentControls
        If IsManaged(cc) Then cc.Appearance = wdContentControlBoundingBox
    Next cc
    MsgBox "Final render stopped; stale or failed blocks stayed editable.", vbExclamation
End Sub
