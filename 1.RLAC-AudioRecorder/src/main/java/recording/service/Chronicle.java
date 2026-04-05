package recording.service;

public class Chronicle {
    private String nomDeChronique;
    private Integer startTime;
    private Integer endTime;

    public Chronicle(String nomDeChronique, Integer startTime, Integer endTime) {
        this.nomDeChronique = nomDeChronique;
        this.startTime = startTime;
        this.endTime = endTime;
    }

    public String getNomDeChronique() {
        return nomDeChronique;
    }

    public void setNomDeChronique(String nomDeChronique) {
        this.nomDeChronique = nomDeChronique;
    }

    public Integer getStartTime() {
        return startTime;
    }

    public void setStartTime(Integer startTime) {
        this.startTime = startTime;
    }

    public Integer getEndTime() {
        return endTime;
    }

    public void setEndTime(Integer endTime) {
        this.endTime = endTime;
    }
}
